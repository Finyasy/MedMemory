def test_list_records_empty(client):
    response = client.get("/api/v1/records")

    assert response.status_code == 200
    assert response.json() == []


def test_create_and_get_record(client):
    patient_id = 1
    payload = {
        "title": "Annual Physical",
        "content": "Vitals are normal.",
        "record_type": "visit_note",
    }

    create_response = client.post(
        f"/api/v1/records?patient_id={patient_id}",
        json=payload,
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"] == 1
    assert created["title"] == payload["title"]
    assert created["content"] == payload["content"]
    assert created["record_type"] == payload["record_type"]
    assert created["patient_id"] == patient_id
    assert "created_at" in created

    list_response = client.get("/api/v1/records")

    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["title"] == payload["title"]
    assert listed[0]["content"] == payload["content"]
    assert listed[0]["record_type"] == payload["record_type"]
    assert listed[0]["patient_id"] == patient_id
    assert "created_at" in listed[0]

    get_response = client.get("/api/v1/records/1")

    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == created["id"]
    assert fetched["title"] == payload["title"]
    assert fetched["content"] == payload["content"]
    assert fetched["record_type"] == payload["record_type"]
    assert fetched["patient_id"] == patient_id
    assert "created_at" in fetched


def test_get_record_missing(client):
    response = client.get("/api/v1/records/999")

    assert response.status_code == 404
