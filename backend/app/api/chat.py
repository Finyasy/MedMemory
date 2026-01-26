"""Chat API endpoints for medical Q&A.

Provides conversational interface using RAG with MedGemma-4B-IT.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.database import get_db
from app.models import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
    LLMInfoResponse,
    MessageSchema,
    SourceInfo,
    StreamChatChunk,
    VolumeChatResponse,
    CxrCompareResponse,
    LocalizationResponse,
    WsiChatResponse,
    VisionChatResponse,
)
from app.services.imaging import (
    build_volume_montage,
    build_volume_montage_from_array,
    build_wsi_montage,
    filter_image_filenames,
    load_dicom_volume,
    load_nifti_volume,
)
from app.services.llm import LLMService, RAGService
from app.services.llm.conversation import ConversationManager

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/llm/info", response_model=LLMInfoResponse)
async def get_llm_info():
    """Get information about the loaded LLM model."""
    llm_service = LLMService.get_instance()
    info = llm_service.get_model_info()
    return LLMInfoResponse(**info)


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def _parse_localization_payload(payload: str, width: int, height: int) -> list[dict]:
    import json

    if not payload:
        return []
    parsed = None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        start = payload.find("{")
        end = payload.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(payload[start : end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(parsed, dict):
        return []
    boxes = parsed.get("boxes", [])
    if not isinstance(boxes, list):
        return []
    results = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        label = str(box.get("label", "finding"))
        confidence = float(box.get("confidence", 0.0) or 0.0)
        x_min = _clamp(float(box.get("x_min", 0.0) or 0.0))
        y_min = _clamp(float(box.get("y_min", 0.0) or 0.0))
        x_max = _clamp(float(box.get("x_max", 0.0) or 0.0))
        y_max = _clamp(float(box.get("y_max", 0.0) or 0.0))
        px_min = int(round(x_min * width))
        py_min = int(round(y_min * height))
        px_max = int(round(x_max * width))
        py_max = int(round(y_max * height))
        results.append(
            {
                "label": label,
                "confidence": confidence,
                "x_min": px_min,
                "y_min": py_min,
                "x_max": px_max,
                "y_max": py_max,
                "x_min_norm": x_min,
                "y_min_norm": y_min,
                "x_max_norm": x_max,
                "y_max_norm": y_max,
            }
        )
    return results


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ask a question about a patient using RAG.
    
    This endpoint:
    1. Retrieves relevant context from patient records
    2. Generates an answer using MedGemma-4B-IT
    3. Stores the conversation for history
    
    Example questions:
    - "What medications is the patient currently taking?"
    - "Show me any abnormal lab results from the past year"
    - "What is the patient's diagnosis history?"
    """
    # Verify patient exists
    await get_patient_for_user(
        patient_id=request.patient_id,
        db=db,
        current_user=current_user,
    )
    
    # Run RAG
    rag_service = RAGService(db)
    rag_response = await rag_service.ask(
        question=request.question,
        patient_id=request.patient_id,
        conversation_id=request.conversation_id,
        system_prompt=request.system_prompt,
        max_context_tokens=request.max_context_tokens,
        use_conversation_history=request.use_conversation_history,
    )
    
    return ChatResponse(
        answer=rag_response.answer,
        conversation_id=rag_response.conversation_id,
        message_id=rag_response.message_id,
        num_sources=rag_response.num_sources,
        sources=[
            SourceInfo(
                source_type=s["source_type"],
                source_id=s["source_id"],
                relevance=s["relevance"],
            )
            for s in rag_response.sources_summary
        ],
        tokens_input=rag_response.llm_response.tokens_input,
        tokens_generated=rag_response.llm_response.tokens_generated,
        tokens_total=rag_response.llm_response.total_tokens,
        context_time_ms=rag_response.context_time_ms,
        generation_time_ms=rag_response.generation_time_ms,
        total_time_ms=rag_response.total_time_ms,
    )


@router.post("/stream")
async def stream_ask(
    question: str = Query(..., min_length=1, max_length=2000),
    patient_id: int = Query(...),
    conversation_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Stream answer generation token by token.
    
    Useful for real-time chat interfaces where you want to show
    the answer as it's being generated.
    """
    # Verify patient exists
    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )
    
    # Get or create conversation
    manager = ConversationManager(db)
    conversation_uuid = conversation_id
    if conversation_uuid is None:
        conversation = await manager.create_conversation(patient_id=patient_id)
        conversation_uuid = conversation.conversation_id
    
    rag_service = RAGService(db)
    
    async def generate():
        async for chunk in rag_service.stream_ask(
            question=question,
            patient_id=patient_id,
            conversation_id=conversation_uuid,
        ):
            yield f"data: {StreamChatChunk(chunk=chunk, conversation_id=conversation_uuid, is_complete=False).model_dump_json()}\n\n"
        
        # Send completion with conversation ID
        yield f"data: {StreamChatChunk(chunk='', conversation_id=conversation_uuid, is_complete=True).model_dump_json()}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/vision", response_model=VisionChatResponse)
async def ask_with_image(
    prompt: str = Form(..., min_length=1, max_length=2000),
    patient_id: int = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Analyze a medical image using the vision-language model."""
    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    llm_service = LLMService.get_instance()
    user_prompt = f"""You are a medical imaging AI assistant. Analyze this medical image and provide findings.

Task: {prompt}

Describe the key findings in this image in 3-5 sentences. Include:
- Image type and quality assessment
- Normal anatomical structures visible
- Any abnormal findings or areas of concern
- Overall impression

Findings:"""

    llm_response = await llm_service.generate_with_image(
        prompt=user_prompt,
        image_bytes=image_bytes,
        system_prompt=None,
        max_new_tokens=300,
    )

    return VisionChatResponse(
        answer=llm_response.text,
        tokens_input=llm_response.tokens_input,
        tokens_generated=llm_response.tokens_generated,
        tokens_total=llm_response.total_tokens,
        generation_time_ms=llm_response.generation_time_ms,
    )


@router.post("/volume", response_model=VolumeChatResponse)
async def ask_with_volume(
    prompt: str = Form(..., min_length=1, max_length=2000),
    patient_id: int = Form(...),
    slices: list[UploadFile] = File(...),
    sample_count: int = Form(9),
    tile_size: int = Form(256),
    modality: str = Form("CT"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Analyze a CT/MRI volume provided as a stack of 2D slices."""
    import io
    import zipfile

    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )

    if not slices:
        raise HTTPException(status_code=400, detail="No slices provided.")

    if sample_count < 3 or sample_count > 25:
        raise HTTPException(status_code=400, detail="sample_count must be between 3 and 25.")

    if tile_size < 128 or tile_size > 512:
        raise HTTPException(status_code=400, detail="tile_size must be between 128 and 512.")

    first = slices[0]
    is_zip = (
        len(slices) == 1
        and (
            (first.content_type and first.content_type in {"application/zip", "application/x-zip-compressed"})
            or (first.filename and first.filename.lower().endswith(".zip"))
        )
    )

    montage = None
    total_slices = 0
    sampled_indices: list[int] = []
    grid_rows = 0
    grid_cols = 0
    tile_size_value = tile_size

    if len(slices) == 1 and first.filename:
        lowered = first.filename.lower()
        if lowered.endswith(".nii") or lowered.endswith(".nii.gz"):
            nifti_bytes = await first.read()
            if not nifti_bytes:
                raise HTTPException(status_code=400, detail="Empty NIfTI upload.")
            volume = load_nifti_volume(nifti_bytes)
            montage = build_volume_montage_from_array(
                volume=volume,
                sample_count=sample_count,
                tile_size=tile_size,
            )
    if montage is None and is_zip:
        archive_bytes = await first.read()
        if not archive_bytes:
            raise HTTPException(status_code=400, detail="Empty zip upload.")
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            all_names = sorted(zf.namelist())
            dicom_names = [name for name in all_names if name.lower().endswith(".dcm")]
            if dicom_names:
                dicom_bytes = [zf.read(name) for name in dicom_names if not name.endswith("/")]
                volume = load_dicom_volume(dicom_bytes)
                montage = build_volume_montage_from_array(
                    volume=volume,
                    sample_count=sample_count,
                    tile_size=tile_size,
                )
            else:
                names = filter_image_filenames(all_names)
                if not names:
                    raise HTTPException(
                        status_code=400,
                        detail="Zip contains no supported image or DICOM slices.",
                    )
                slice_bytes = [zf.read(name) for name in names if not name.endswith("/")]
                if len(slice_bytes) < 3:
                    raise HTTPException(status_code=400, detail="At least 3 slices are required.")
                montage = build_volume_montage(
                    slice_images=slice_bytes,
                    sample_count=sample_count,
                    tile_size=tile_size,
                )

    if montage is None:
        slice_bytes: list[bytes] = []
        ordered = sorted(slices, key=lambda item: item.filename or "")
        for upload in ordered:
            if upload.content_type and upload.content_type.startswith("image/"):
                pass
            elif upload.filename and filter_image_filenames([upload.filename]):
                pass
            elif upload.filename and upload.filename.lower().endswith(".dcm"):
                raise HTTPException(
                    status_code=400,
                    detail="DICOM series must be uploaded as a .zip of slices.",
                )
            else:
                raise HTTPException(status_code=400, detail="All slices must be image files.")
            payload = await upload.read()
            if not payload:
                raise HTTPException(status_code=400, detail="Empty slice upload.")
            slice_bytes.append(payload)

        if len(slice_bytes) < 3:
            raise HTTPException(status_code=400, detail="At least 3 slices are required.")

        montage = build_volume_montage(
            slice_images=slice_bytes,
            sample_count=sample_count,
            tile_size=tile_size,
        )

    total_slices = montage.total_slices
    sampled_indices = montage.sampled_indices
    grid_rows, grid_cols = montage.grid
    tile_size_value = montage.tile_size[0]

    llm_service = LLMService.get_instance()
    user_prompt = f"""You are a radiologist AI assistant analyzing a 3D medical volume.

Modality: {modality}
Volume Info: Showing {len(montage.sampled_indices)} representative slices from {montage.total_slices} total slices.

Task: {prompt}

Analyze this volume montage and provide findings:
- Image quality and technical assessment
- Normal anatomical structures
- Any pathological findings
- Recommendations for follow-up if needed

Findings:"""

    llm_response = await llm_service.generate_with_image(
        prompt=user_prompt,
        image_bytes=montage.montage_bytes,
        system_prompt=None,
        max_new_tokens=350,
    )

    return VolumeChatResponse(
        answer=llm_response.text,
        total_slices=total_slices,
        sampled_indices=sampled_indices,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        tile_size=tile_size_value,
        tokens_input=llm_response.tokens_input,
        tokens_generated=llm_response.tokens_generated,
        tokens_total=llm_response.total_tokens,
        generation_time_ms=llm_response.generation_time_ms,
    )


@router.post("/wsi", response_model=WsiChatResponse)
async def ask_with_wsi(
    prompt: str = Form(..., min_length=1, max_length=2000),
    patient_id: int = Form(...),
    patches: list[UploadFile] = File(...),
    sample_count: int = Form(12),
    tile_size: int = Form(256),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Analyze WSI patches provided as multiple images or a zip."""
    import io
    import zipfile

    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )

    if not patches:
        raise HTTPException(status_code=400, detail="No patches provided.")

    if sample_count < 4 or sample_count > 36:
        raise HTTPException(status_code=400, detail="sample_count must be between 4 and 36.")

    if tile_size < 128 or tile_size > 512:
        raise HTTPException(status_code=400, detail="tile_size must be between 128 and 512.")

    first = patches[0]
    is_zip = (
        len(patches) == 1
        and (
            (first.content_type and first.content_type in {"application/zip", "application/x-zip-compressed"})
            or (first.filename and first.filename.lower().endswith(".zip"))
        )
    )

    patch_bytes: list[bytes] = []
    if is_zip:
        archive_bytes = await first.read()
        if not archive_bytes:
            raise HTTPException(status_code=400, detail="Empty zip upload.")
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            names = filter_image_filenames(sorted(zf.namelist()))
            if not names:
                raise HTTPException(status_code=400, detail="Zip contains no supported patch images.")
            patch_bytes = [zf.read(name) for name in names if not name.endswith("/")]
    else:
        ordered = sorted(patches, key=lambda item: item.filename or "")
        for upload in ordered:
            if upload.content_type and upload.content_type.startswith("image/"):
                pass
            elif upload.filename and filter_image_filenames([upload.filename]):
                pass
            else:
                raise HTTPException(status_code=400, detail="All patches must be image files.")
            payload = await upload.read()
            if not payload:
                raise HTTPException(status_code=400, detail="Empty patch upload.")
            patch_bytes.append(payload)

    if len(patch_bytes) < 4:
        raise HTTPException(status_code=400, detail="At least 4 patch images are required.")

    montage = build_wsi_montage(
        patch_images=patch_bytes,
        sample_count=sample_count,
        tile_size=tile_size,
    )

    llm_service = LLMService.get_instance()
    wsi_prompt = f"""You are a pathologist AI assistant analyzing whole-slide histopathology images.

Patches shown: {len(montage.sampled_indices)} representative regions from the slide.

Task: {prompt}

Analyze these tissue patches and provide findings:
- Tissue type and specimen quality
- Cellular morphology and architecture
- Any abnormal features or pathological changes
- Differential considerations

Findings:"""

    sampled_patch_bytes = [patch_bytes[idx] for idx in montage.sampled_indices]
    try:
        llm_response = await llm_service.generate_with_images(
            prompt=wsi_prompt,
            images_bytes=sampled_patch_bytes,
            system_prompt=None,
            max_new_tokens=350,
        )
        grid_rows, grid_cols = 0, 0
        tile_size_value = tile_size
    except Exception:
        llm_response = await llm_service.generate_with_image(
            prompt=wsi_prompt,
            image_bytes=montage.montage_bytes,
            system_prompt=None,
            max_new_tokens=350,
        )
        grid_rows, grid_cols = montage.grid
        tile_size_value = montage.tile_size[0]

    return WsiChatResponse(
        answer=llm_response.text,
        total_patches=len(patch_bytes),
        sampled_indices=montage.sampled_indices,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        tile_size=tile_size_value,
        tokens_input=llm_response.tokens_input,
        tokens_generated=llm_response.tokens_generated,
        tokens_total=llm_response.total_tokens,
        generation_time_ms=llm_response.generation_time_ms,
    )


@router.post("/cxr/compare", response_model=CxrCompareResponse)
async def compare_cxr(
    prompt: str = Form(..., min_length=1, max_length=2000),
    patient_id: int = Form(...),
    current_image: UploadFile = File(...),
    prior_image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Compare a current and prior chest X-ray."""
    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )

    if not current_image.content_type or not current_image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Current image must be an image file.")
    if not prior_image.content_type or not prior_image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Prior image must be an image file.")

    current_bytes = await current_image.read()
    prior_bytes = await prior_image.read()
    if not current_bytes or not prior_bytes:
        raise HTTPException(status_code=400, detail="Both images must be provided.")

    llm_service = LLMService.get_instance()
    cxr_prompt = f"""You are a radiologist AI assistant comparing chest X-rays over time.

Images provided:
- Image 1: Current chest X-ray
- Image 2: Prior chest X-ray

Task: {prompt}

Compare these chest X-rays and describe interval changes:
- Technical comparison (positioning, exposure)
- Cardiac silhouette changes
- Lung field changes
- Mediastinal and hilar changes
- Any new, resolved, or progressing findings

Interval Change Report:"""

    llm_response = await llm_service.generate_with_images(
        prompt=cxr_prompt,
        images_bytes=[current_bytes, prior_bytes],
        system_prompt=None,
        max_new_tokens=400,
    )

    return CxrCompareResponse(
        answer=llm_response.text,
        tokens_input=llm_response.tokens_input,
        tokens_generated=llm_response.tokens_generated,
        tokens_total=llm_response.total_tokens,
        generation_time_ms=llm_response.generation_time_ms,
    )


@router.post("/localize", response_model=LocalizationResponse)
async def localize_findings(
    prompt: str = Form(..., min_length=1, max_length=2000),
    patient_id: int = Form(...),
    image: UploadFile | None = File(None),
    slices: list[UploadFile] | None = File(None),
    patches: list[UploadFile] | None = File(None),
    sample_count: int = Form(9),
    tile_size: int = Form(256),
    modality: str = Form("unknown"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Localize findings with bounding boxes for multiple modalities."""
    import io
    import zipfile
    from PIL import Image

    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )

    if image is None and not slices and not patches:
        raise HTTPException(status_code=400, detail="Provide image, slices, or patches.")

    montage_bytes: bytes | None = None

    if image is not None:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Image must be an image file.")
        montage_bytes = await image.read()
    elif slices:
        first = slices[0]
        is_zip = (
            len(slices) == 1
            and (
                (first.content_type and first.content_type in {"application/zip", "application/x-zip-compressed"})
                or (first.filename and first.filename.lower().endswith(".zip"))
            )
        )
        if len(slices) == 1 and first.filename and first.filename.lower().endswith((".nii", ".nii.gz")):
            nifti_bytes = await first.read()
            volume = load_nifti_volume(nifti_bytes)
            montage = build_volume_montage_from_array(
                volume=volume,
                sample_count=sample_count,
                tile_size=tile_size,
            )
            montage_bytes = montage.montage_bytes
        elif is_zip:
            archive_bytes = await first.read()
            if not archive_bytes:
                raise HTTPException(status_code=400, detail="Empty zip upload.")
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                all_names = sorted(zf.namelist())
                dicom_names = [name for name in all_names if name.lower().endswith(".dcm")]
                if dicom_names:
                    dicom_bytes = [zf.read(name) for name in dicom_names if not name.endswith("/")]
                    volume = load_dicom_volume(dicom_bytes)
                    montage = build_volume_montage_from_array(
                        volume=volume,
                        sample_count=sample_count,
                        tile_size=tile_size,
                    )
                    montage_bytes = montage.montage_bytes
                else:
                    names = filter_image_filenames(all_names)
                    if not names:
                        raise HTTPException(status_code=400, detail="Zip contains no supported images.")
                    slice_bytes = [zf.read(name) for name in names if not name.endswith("/")]
                    montage = build_volume_montage(
                        slice_images=slice_bytes,
                        sample_count=sample_count,
                        tile_size=tile_size,
                    )
                    montage_bytes = montage.montage_bytes
        else:
            ordered = sorted(slices, key=lambda item: item.filename or "")
            slice_bytes = [await upload.read() for upload in ordered]
            montage = build_volume_montage(
                slice_images=slice_bytes,
                sample_count=sample_count,
                tile_size=tile_size,
            )
            montage_bytes = montage.montage_bytes
    elif patches:
        first = patches[0]
        is_zip = (
            len(patches) == 1
            and (
                (first.content_type and first.content_type in {"application/zip", "application/x-zip-compressed"})
                or (first.filename and first.filename.lower().endswith(".zip"))
            )
        )
        patch_bytes = []
        if is_zip:
            archive_bytes = await first.read()
            if not archive_bytes:
                raise HTTPException(status_code=400, detail="Empty zip upload.")
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                names = filter_image_filenames(sorted(zf.namelist()))
                if not names:
                    raise HTTPException(status_code=400, detail="Zip contains no supported patch images.")
                patch_bytes = [zf.read(name) for name in names if not name.endswith("/")]
        else:
            patch_bytes = [await upload.read() for upload in patches]
        montage = build_wsi_montage(
            patch_images=patch_bytes,
            sample_count=sample_count,
            tile_size=tile_size,
        )
        montage_bytes = montage.montage_bytes

    if montage_bytes is None:
        raise HTTPException(status_code=400, detail="Unable to build image for localization.")

    image_obj = Image.open(io.BytesIO(montage_bytes))
    width, height = image_obj.size

    llm_service = LLMService.get_instance()
    localize_prompt = f"""You are a radiologist AI assistant performing anatomical localization.

Modality: {modality}
Task: {prompt}

Localize findings in this image. Return a JSON response with:
1. "summary": Brief description of the image
2. "boxes": Array of findings with bounding boxes

Each box should have:
- "label": Name of the finding or structure
- "confidence": Confidence score (0.0-1.0)
- "x_min", "y_min", "x_max", "y_max": Normalized coordinates (0.0-1.0)

Respond with JSON only:
{{"summary": "description", "boxes": [{{"label": "finding", "confidence": 0.8, "x_min": 0.1, "y_min": 0.2, "x_max": 0.3, "y_max": 0.4}}]}}

JSON Response:"""

    llm_response = await llm_service.generate_with_image(
        prompt=localize_prompt,
        image_bytes=montage_bytes,
        system_prompt=None,
        max_new_tokens=500,
    )
    boxes = _parse_localization_payload(llm_response.text, width, height)
    if not boxes:
        strict_prompt = (
            "Return JSON only. Do not include markdown, code fences, or commentary. "
            "Use keys: summary, boxes. boxes is an array of objects with label, confidence, x_min, y_min, x_max, y_max."
        )
        llm_response = await llm_service.generate_with_image(
            prompt=f"{prompt}\nModality: {modality}",
            image_bytes=montage_bytes,
            system_prompt=strict_prompt,
            max_new_tokens=240,
        )
        boxes = _parse_localization_payload(llm_response.text, width, height)

    return LocalizationResponse(
        answer=llm_response.text,
        boxes=boxes,
        image_width=width,
        image_height=height,
        tokens_input=llm_response.tokens_input,
        tokens_generated=llm_response.tokens_generated,
        tokens_total=llm_response.total_tokens,
        generation_time_ms=llm_response.generation_time_ms,
    )


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create a new conversation."""
    # Verify patient exists
    await get_patient_for_user(
        patient_id=request.patient_id,
        db=db,
        current_user=current_user,
    )
    
    manager = ConversationManager(db)
    conversation = await manager.create_conversation(
        patient_id=request.patient_id,
        title=request.title,
    )
    
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        patient_id=conversation.patient_id,
        title=conversation.title or "New Conversation",
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get a conversation with all messages."""
    manager = ConversationManager(db)
    conversation = await manager.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await get_patient_for_user(
        patient_id=conversation.patient_id,
        db=db,
        current_user=current_user,
    )
    
    return ConversationDetail(
        conversation_id=conversation.conversation_id,
        patient_id=conversation.patient_id,
        title=conversation.title or "Conversation",
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        messages=[
            MessageSchema(
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp,
                message_id=msg.message_id,
            )
            for msg in conversation.messages
        ],
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    patient_id: int = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List conversations for a patient."""
    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )
    manager = ConversationManager(db)
    conversations = await manager.list_conversations(patient_id, limit)
    
    return [
        ConversationResponse(
            conversation_id=conv.conversation_id,
            patient_id=conv.patient_id,
            title=conv.title or "Conversation",
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages),
        )
        for conv in conversations
    ]


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    manager = ConversationManager(db)
    deleted = await manager.delete_conversation(conversation_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.patch("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: UUID,
    title: str = Query(..., min_length=1, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    """Update conversation title."""
    manager = ConversationManager(db)
    updated = await manager.update_title(conversation_id, title)
    
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"title": title}
