import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.text_preprocessor import TextPreprocessor
from backend.services.semantic_matcher import SemanticMatcher
from backend.services.rubric_grader import RubricGrader
from backend.services.feedback_generator import FeedbackGenerator
from backend.services.pdf_extractor import DocumentExtractorService

client = TestClient(app)


# ---------------------------------------------------------------------------
# PHASE 1 & 2 REGRESSION TESTS
# ---------------------------------------------------------------------------

def test_health_endpoint():
    response = client.get("/api/ps2/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "EDUCORE AI - PS2" in data["service"]
    assert "version" in data


def test_list_assessments():
    response = client.get("/api/ps2/assessments")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1


def test_list_submissions():
    response = client.get("/api/ps2/submissions")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_rubric_sum_validation_failure():
    invalid_assessment = {
        "title": "Invalid Rubric Assessment",
        "course_code": "CS-999",
        "faculty_id": "FAC_TEST",
        "max_score": 20.0,
        "questions": [
            {
                "question_number": 1,
                "question_text": "Sample Question",
                "max_marks": 20.0,
                "model_answer": "Sample reference answer.",
                "rubrics": [
                    {"criterion_name": "Crit A", "max_points": 10.0, "weight": 1.0, "levels": []},
                    {"criterion_name": "Crit B", "max_points": 5.0, "weight": 1.0, "levels": []}
                ]
            }
        ]
    }
    response = client.post("/api/ps2/assessments", json=invalid_assessment)
    assert response.status_code == 422


def test_txt_and_pdf_submission_and_extraction():
    txt_content = (
        "In a distributed system, network partitions will inevitably happen due to cable cuts or packet loss. "
        "Therefore, according to the CAP theorem, the system architect must choose between Consistency and Availability. "
        "If choosing CP, the system rejects writes to preserve consistency during a split brain."
    )
    response = client.post(
        "/api/ps2/assessments/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d/submissions",
        data={"student_id": "EDU_STU_2026_TEST1", "student_name": "Test User"},
        files={"file": ("test.txt", txt_content.encode("utf-8"), "text/plain")}
    )
    assert response.status_code == 201
    assert response.json()["data"]["extraction_status"] == "success"


def test_unsupported_file_and_empty_guard():
    # Unsupported file
    res = client.post(
        "/api/ps2/assessments/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d/submissions",
        data={"student_id": "EDU_STU_2026_FAIL"},
        files={"file": ("bad.exe", b"MZ fake executable", "application/octet-stream")}
    )
    assert res.status_code == 400

    # Empty file
    res2 = client.post(
        "/api/ps2/assessments/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d/submissions",
        data={"student_id": "EDU_STU_2026_EMPTY"},
        files={"file": ("empty.txt", b"", "text/plain")}
    )
    assert res2.status_code == 400


# ---------------------------------------------------------------------------
# PHASE 3: AI-POWERED GRADING ENGINE TESTS
# ---------------------------------------------------------------------------

@pytest.fixture
def red_black_tree_question_setup():
    model_answer = (
        "A Red-Black Tree maintains balance via five primary invariants: (1) Every node is red or black, "
        "(2) The root is black, (3) Every leaf NIL is black, (4) If a node is red, both children are black, "
        "and (5) All simple paths from any node to descendant leaves contain the same black-height bh(x). "
        "When inserting a red node, violations occur if parent is red. If uncle is red, we execute a color flip. "
        "If uncle is black and there is a zig-zag configuration, a tree rotation aligns it into a straight line, "
        "followed by a rotation and recoloring. The maximum height is at most 2*log2(n+1), guaranteeing O(log n) time."
    )
    key_concepts = [
        "red-black invariants",
        "black-height",
        "uncle node",
        "color flip",
        "tree rotations",
        "height bound 2*log(n+1)"
    ]
    rubrics = [
        {
            "criterion_name": "Invariants & Core Theory",
            "description": "Accurate explanation of Red-Black invariants including black-height consistency.",
            "max_points": 8.0,
            "weight": 1.0,
            "levels": []
        },
        {
            "criterion_name": "Insertion Rebalancing Logic",
            "description": "Clear distinction between uncle-red recoloring and uncle-black rotations.",
            "max_points": 10.0,
            "weight": 1.0,
            "levels": []
        },
        {
            "criterion_name": "Mathematical Height Proof",
            "description": "Proof of the upper height bound 2*log(n+1) and logarithmic complexity.",
            "max_points": 7.0,
            "weight": 1.0,
            "levels": []
        }
    ]
    return {
        "model_answer": model_answer,
        "key_concepts": key_concepts,
        "rubrics": rubrics,
        "max_marks": 25.0
    }


def test_strong_student_answer_evaluation(red_black_tree_question_setup):
    """
    Demo Strong Answer: Student articulates all 5 invariants, uncle recoloring, rotations,
    and asymptotic proof.
    Verifies: High marks (>= 20/25), identified concepts, supporting evidence excerpts, exemplary feedback.
    """
    strong_student_answer = (
        "Red-Black Trees maintain balance through node color properties and rotations. "
        "Every node is colored red or black, root is always black, NIL leaves are black. "
        "Red nodes cannot have red children (no consecutive red nodes), and every path from root to leaf "
        "has the exact same black-height bh(x). When adding a new node, it is initially colored red. "
        "If its uncle node is red, we recolor parent and uncle to black and grandparent to red (color flip). "
        "If uncle is black, we perform tree rotations (single or double rotations) depending on zig-zag alignment. "
        "Because no path has more than double the nodes of the shortest path, height is strictly bounded by 2*log2(n+1), "
        "ensuring O(log n) operations."
    )

    grader = RubricGrader()
    feedback_gen = FeedbackGenerator()
    setup = red_black_tree_question_setup

    grade = grader.grade_answer(
        student_answer=strong_student_answer,
        model_answer=setup["model_answer"],
        key_concepts=setup["key_concepts"],
        rubrics=setup["rubrics"],
        max_marks=setup["max_marks"],
        required_concepts=["black-height", "uncle node", "tree rotations", "height bound 2*log(n+1)"]
    )

    # 1. Marks check
    assert grade["ai_score"] >= 20.0
    assert grade["ai_score"] <= setup["max_marks"]

    # 2. Evidence generation check
    assert len(grade["supporting_evidence"]) > 0
    assert any("black-height" in ev for ev in grade["supporting_evidence"])

    # 3. Concepts check
    assert "black-height" in grade["identified_concepts"]
    assert "tree rotations" in grade["identified_concepts"]

    # 4. Criterion scores check
    assert len(grade["rubric_scores"]) == 3
    for crit in grade["rubric_scores"]:
        assert crit["assigned_points"] > 0
        assert crit["assigned_points"] <= crit["max_points"]
        assert crit["evidence_coverage"] > 0.60

    # 5. Feedback generation
    feedback = feedback_gen.generate_feedback(
        student_answer=strong_student_answer,
        model_answer=setup["model_answer"],
        grading_result=grade
    )
    assert len(feedback["correctly_explained"]) > 0
    assert "Exemplary" in feedback["feedback"] or "Proficient" in feedback["feedback"]


def test_partially_correct_and_paraphrased_answer(red_black_tree_question_setup):
    """
    Demo Partially Correct Answer: Student uses different phrasing and covers invariants & rotations,
    but completely omits the mathematical proof for the height bound.
    Verifies: Partial credit (14-19 / 25), missing concept correctly identifies height proof,
    criterion 3 scores low.
    """
    partial_student_answer = (
        "In a red black search tree, vertices are given color tags red and black to keep height short. "
        "Root is black and leaves are black. Two red vertices cannot touch each other. "
        "When inserting, we check parent's sibling. If uncle is red, recolor both parent and uncle. "
        "If uncle is black, we fix it by doing rotations around the node."
    )

    grader = RubricGrader()
    feedback_gen = FeedbackGenerator()
    setup = red_black_tree_question_setup

    grade = grader.grade_answer(
        student_answer=partial_student_answer,
        model_answer=setup["model_answer"],
        key_concepts=setup["key_concepts"],
        rubrics=setup["rubrics"],
        max_marks=setup["max_marks"],
        required_concepts=["black-height", "uncle node", "tree rotations", "height bound 2*log(n+1)"]
    )

    # Partial score
    assert 10.0 <= grade["ai_score"] < 21.0
    # Missing required concepts
    assert "height bound 2*log(n+1)" in grade["missing_concepts"] or "black-height" in grade["missing_concepts"]

    feedback = feedback_gen.generate_feedback(
        student_answer=partial_student_answer,
        model_answer=setup["model_answer"],
        grading_result=grade
    )
    assert len(feedback["how_to_improve"]) > 0


def test_weak_student_answer(red_black_tree_question_setup):
    """
    Demo Weak Answer: Very brief with no explanation of mechanics.
    Verifies: Low marks (< 10/25), warnings about brevity, missing concepts identified.
    """
    weak_student_answer = "Red-black trees have red and black nodes and stay balanced in log n time."

    grader = RubricGrader()
    setup = red_black_tree_question_setup

    grade = grader.grade_answer(
        student_answer=weak_student_answer,
        model_answer=setup["model_answer"],
        key_concepts=setup["key_concepts"],
        rubrics=setup["rubrics"],
        max_marks=setup["max_marks"],
        required_concepts=["black-height", "uncle node", "tree rotations", "height bound 2*log(n+1)"]
    )

    assert grade["ai_score"] < 10.0
    assert len(grade["missing_concepts"]) >= 2
    assert len(grade["warnings"]) > 0


def test_contradictory_claim_detection(red_black_tree_question_setup):
    """
    Demo Contradictory Claim: Student states 'Red nodes can have red children'.
    Verifies: Contradiction identified in incorrect_concepts, penalty applied to correctness.
    """
    contradictory_answer = (
        "Red-Black trees use colors. Red nodes can have red children in some cases. "
        "Rotations are used when uncle is black."
    )

    grader = RubricGrader()
    setup = red_black_tree_question_setup

    grade = grader.grade_answer(
        student_answer=contradictory_answer,
        model_answer=setup["model_answer"],
        key_concepts=setup["key_concepts"],
        rubrics=setup["rubrics"],
        max_marks=setup["max_marks"]
    )

    assert grade["ai_score"] < 12.0


def test_api_evaluate_endpoint_with_unreadable_guard():
    """
    POST /api/ps2/submissions/{id}/evaluate on empty or unreadable submission must fail with HTTP 400.
    """
    # 1. Create empty submission
    res = client.post(
        "/api/ps2/assessments/a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d/submissions",
        data={"student_id": "EDU_STU_2026_EMPTYTEST"},
        files={"file": ("blank.txt", b"   ", "text/plain")}
    )
    empty_sub_id = res.json()["data"]["id"]

    # 2. Attempt evaluate on empty submission -> Must return 400
    eval_res = client.post(f"/api/ps2/submissions/{empty_sub_id}/evaluate")
    assert eval_res.status_code == 400
    assert "never grade an empty" in eval_res.json()["detail"].lower()


def test_api_evaluate_endpoint_success_and_get():
    """
    POST /api/ps2/submissions/{id}/evaluate on valid submission -> Computes marks, updates status,
    and returns explainable breakdown.
    GET /api/ps2/evaluations/{id} retrieves the evaluation record.
    """
    sub_id = "sub-1001-aaaa-bbbb-cccc-dddddddddddd"
    response = client.post(f"/api/ps2/submissions/{sub_id}/evaluate")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["submission_id"] == sub_id
    assert data["total_score"] > 0
    assert len(data["evaluations"]) >= 1

    eval_item = data["evaluations"][0]
    eval_id = eval_item["id"]
    assert "suggested_marks" in eval_item
    assert "rubric_scores" in eval_item
    assert "supporting_evidence" in eval_item
    assert "grading_method" in eval_item

    # Verify GET /api/ps2/evaluations/{evaluation_id}
    get_res = client.get(f"/api/ps2/evaluations/{eval_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()["data"]
    assert get_data["id"] == eval_id
    assert get_data["submission_id"] == sub_id
