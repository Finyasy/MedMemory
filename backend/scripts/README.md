# Model Download Scripts

Scripts for downloading and managing LLM models for local use.

## Download Model Script

### Usage

Download and quantize MedGemma model for local use:

```bash
python scripts/download_model.py --model-id google/medgemma-1.5-4b-it --output-dir models/medgemma-1.5-4b-it
```

### Options

- `--model-id`: Hugging Face model identifier (default: `google/medgemma-1.5-4b-it`)
- `--output-dir`: Local directory to save the model (default: `models/medgemma-1.5-4b-it`)
- `--no-quantize`: Skip 4-bit quantization (use full precision model)
- `--hf-token`: Hugging Face token for private models (optional)

### Quantization

By default, the script uses **INT4 (4-bit) quantization** with best practices:

- **NF4 quantization type**: Normal Float 4-bit for optimal accuracy
- **Double quantization**: Reduces memory usage further
- **FP16 compute dtype**: Uses float16 for computations while storing weights in 4-bit
- **Automatic device mapping**: Optimizes model placement across GPUs

**Requirements for quantization:**
- CUDA-enabled GPU (NVIDIA)
- `bitsandbytes` package installed
- Sufficient GPU memory (~4-6 GB for 4B model)

### Model Storage

Models are saved to the `models/` directory by default:
```
backend/
├── models/
│   └── medgemma-1.5-4b-it/
│       ├── config.json
│       ├── pytorch_model.bin (or safetensors)
│       ├── tokenizer.json
│       └── ...
```

### Configuration

After downloading, update your `.env` file:

```env
LLM_MODEL=google/medgemma-1.5-4b-it
LLM_MODEL_PATH=models/medgemma-1.5-4b-it
LLM_QUANTIZE_4BIT=true
```

The application will automatically use the local model when `LLM_MODEL_PATH` is set.

### Download Progress

The download process includes:
1. **Download model files** from Hugging Face (~8-10 GB)
2. **Quantize to INT4** if CUDA is available (~4-6 GB final size)
3. **Verify tokenizer** works correctly
4. **Test model loading** to ensure everything works

Check download progress:
```bash
tail -f model_download.log
```

### Troubleshooting

**CUDA not available:**
- Quantization requires CUDA. The script will fall back to full precision if CUDA is not available.
- Full precision models require ~8-10 GB of RAM/VRAM.

**bitsandbytes not installed:**
- Install with: `pip install bitsandbytes`
- Note: bitsandbytes requires CUDA

**Out of memory:**
- Try using 8-bit quantization instead: `--no-quantize` and manually set 8-bit in config
- Or use CPU inference (no quantization)

**Model path not found:**
- Make sure the download completed successfully
- Check that `LLM_MODEL_PATH` in `.env` matches the actual path

### Best Practices

1. **Disk Space**: Ensure you have at least 15-20 GB free for downloading and processing
2. **GPU Memory**: For 4-bit quantization, 6-8 GB GPU memory is recommended
3. **Internet**: Model download requires stable internet connection (~8-10 GB download)
4. **Time**: Download and quantization can take 10-30 minutes depending on hardware
