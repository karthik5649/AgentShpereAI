import pytest


def test_one_click_contact_sending(client, fake_db):
    # 1. Insert a pending contact
    contact_id = "cont_test_1"
    fake_db.contacts.docs[contact_id] = {
        "_id": contact_id,
        "name": "Sarah Jenkins",
        "email": "sarah.jenkins@synthetix.io",
        "company": "Synthetix AI",
        "title": "VP of Sales",
        "workflow_id": "wf_test_1",
        "company_id": "co_test_1",
        "approval_status": "pending",
        "user_id": "user_test",
    }

    # 2. Attempt to send email to pending contact -> Must fail with 409
    res_pending = client.post(f"/api/v1/contacts/{contact_id}/send")
    assert res_pending.status_code == 409
    assert "approved" in res_pending.json()["detail"].lower()

    # 3. Approve contact
    fake_db.contacts.docs[contact_id]["approval_status"] = "approved"

    # 4. Attempt to send email to approved contact -> Must succeed 200
    res_approved = client.post(
        f"/api/v1/contacts/{contact_id}/send",
        json={"subject": "Custom subject line", "body": "Custom email body content"},
    )
    assert res_approved.status_code == 200
    data = res_approved.json()
    assert data["status"] == "sent"
    assert data["contact_id"] == contact_id
    assert data["recipient"] == "sarah.jenkins@synthetix.io"
    assert data["message_id"] is not None

    # 5. Check email activity was recorded in Mongo
    assert len(fake_db.email_activities.docs) == 1
    activity = list(fake_db.email_activities.docs.values())[0]
    assert activity["contact_id"] == contact_id
    assert activity["recipient"] == "sarah.jenkins@synthetix.io"
    assert activity["subject"] == "Custom subject line"
    assert activity["status"] == "sent"


def test_one_click_contact_not_found(client):
    res = client.post("/api/v1/contacts/non_existent_contact/send")
    assert res.status_code == 404
