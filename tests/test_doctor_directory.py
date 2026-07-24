"""Speciality matching and nearby-facility doctor directory tests."""
from backend.services.doctor_directory import external_doctors, speciality_requirements


def test_chest_pain_prioritizes_cardiology():
    required = speciality_requirements("I have chest pain", "emergency")
    doctors = external_doctors("District Hospital Gadchiroli", required)
    assert required[0] == "Cardiology"
    assert doctors[0]["speciality"] == "Cardiology"
    assert doctors[0]["matches_problem"] is True


def test_problem_categories_have_different_specialities():
    maternity = speciality_requirements("pregnancy labour", "maternity")
    child = speciality_requirements("my child has a fever", "pediatric")
    trauma = speciality_requirements("injury fracture", "trauma")
    assert maternity[0] == "Obstetrics & Gynaecology"
    assert child[0] == "Paediatrics"
    assert trauma[0] == "Orthopaedics"


def test_labour_pain_keeps_obgyn_as_the_primary_speciality():
    required = speciality_requirements("severe labour pain", "emergency")
    doctors = external_doctors("District Hospital Gadchiroli", required)
    assert required[0] == "Obstetrics & Gynaecology"
    assert doctors[0]["speciality"] == "Obstetrics & Gynaecology"


def test_external_directory_exposes_only_public_availability_fields():
    doctors = external_doctors("CHC Aheri", ["Paediatrics"])
    assert doctors and doctors[0]["speciality"] == "Paediatrics"
    allowed = {
        "doctor_id", "name", "speciality", "qualification", "availability_status",
        "availability_tone", "consultation_time", "matches_problem",
    }
    assert all(set(doctor) == allowed for doctor in doctors)
