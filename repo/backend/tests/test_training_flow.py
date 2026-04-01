def _login(client, username: str, password: str = "ChangeMeNow123"):
    client.post("/api/v1/auth/logout")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_training_topic_question_assignment_and_review_cycle(client):
    _login(client, "manager")

    topic = client.post(
        "/api/v1/training/topics",
        json={"code": "POS-POLICY", "name": "POS Policy", "difficulty": "medium"},
    )
    assert topic.status_code == 200

    question = client.post(
        "/api/v1/training/questions",
        json={
            "topic_code": "POS-POLICY",
            "question_text": "What is required for a manual discount override?",
            "option_a": "Cashier PIN",
            "option_b": "Manager override",
            "option_c": "No approval",
            "option_d": "Customer ID only",
            "correct_answer": "Manager override",
        },
    )
    assert question.status_code == 200
    question_id = question.json()["question_id"]

    assignment = client.post(
        "/api/v1/training/assignments",
        json={"employee_username": "employee", "topic_code": "POS-POLICY"},
    )
    assert assignment.status_code == 200

    _login(client, "employee")
    queue_before = client.get("/api/v1/training/review-queue")
    assert queue_before.status_code == 200
    assert any(row["topic_code"] == "POS-POLICY" for row in queue_before.json())

    wrong = client.post(
        "/api/v1/training/attempts",
        json={"topic_code": "POS-POLICY", "question_id": question_id, "selected_answer": "Cashier PIN"},
    )
    assert wrong.status_code == 200
    assert wrong.json()["correct"] is False

    correct = client.post(
        "/api/v1/training/attempts",
        json={"topic_code": "POS-POLICY", "question_id": question_id, "selected_answer": "Manager override"},
    )
    assert correct.status_code == 200
    assert "review in" in correct.json()["recommendation_reason"]

    _login(client, "manager")
    stats = client.get("/api/v1/training/stats")
    assert stats.status_code == 200
    assert any(row["topic_code"] == "POS-POLICY" for row in stats.json())

    trends = client.get("/api/v1/training/trends", params={"days": 14})
    assert trends.status_code == 200
    assert len(trends.json()) >= 1


def test_training_store_isolation(client, db_session):
    from app.services.auth_service import create_user

    create_user(
        db=db_session,
        username="manager102",
        password="ChangeMeNow123",
        display_name="Store Manager 102",
        roles=["store_manager"],
        store_id=102,
    )
    db_session.commit()

    _login(client, "manager")
    topic = client.post(
        "/api/v1/training/topics",
        json={"code": "SAFE-OPS", "name": "Safe Ops", "difficulty": "easy"},
    )
    assert topic.status_code == 200

    _login(client, "manager102")
    topics = client.get("/api/v1/training/topics")
    assert topics.status_code == 200
    assert topics.json() == []

    stats = client.get("/api/v1/training/stats")
    assert stats.status_code == 200
    assert stats.json() == []


def test_training_attempt_requires_active_assignment(client):
    _login(client, "manager")

    topic = client.post(
        "/api/v1/training/topics",
        json={"code": "NO-ASSIGN", "name": "Unassigned Topic", "difficulty": "medium"},
    )
    assert topic.status_code == 200

    question = client.post(
        "/api/v1/training/questions",
        json={
            "topic_code": "NO-ASSIGN",
            "question_text": "Who can approve refunds over policy threshold?",
            "option_a": "Any cashier",
            "option_b": "Supervisor",
            "option_c": "Customer",
            "option_d": "No one",
            "correct_answer": "Supervisor",
        },
    )
    assert question.status_code == 200
    question_id = question.json()["question_id"]

    _login(client, "employee")
    attempt = client.post(
        "/api/v1/training/attempts",
        json={"topic_code": "NO-ASSIGN", "question_id": question_id, "selected_answer": "Supervisor"},
    )
    assert attempt.status_code == 400
    assert attempt.json()["error"]["message"] == "No active assignment for this topic"
