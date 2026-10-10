import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, seed_employees, authenticate_user
from app.auth import create_access_token
from app.ingestion import run_full_ingestion, search_documents
from app.retrieval import secure_search
from app.generation import generate_answer_sync
from app.authorization import get_allowed_access_groups


def setup():
    print("Setting up test environment...")
    init_db()
    seed_employees()
    run_full_ingestion()
    print("Setup complete!\n")


def test_engineering_can_access_rahul_salary():
    print("Test 1: Engineering user asks 'What is Rahul's salary?'")
    print("Expected: ₹65,000 with valid citation")
    
    response = generate_answer_sync("What is Rahul's salary?", "engineering")
    print(f"Answer: {response.answer}")
    print(f"Citations: {[(c.source, c.page, c.row_id) for c in response.citations]}")
    print(f"Retrieved sources: {[(s.source, s.source_type, s.row_id) for s in response.retrieved_sources]}")
    
    assert "65" in response.answer or "₹65" in response.answer, "Should contain salary"
    assert len(response.citations) > 0, "Should have citations"
    print("✓ PASSED\n")


def test_engineering_cannot_access_neha_salary():
    print("Test 2: Engineering user asks 'What is Neha's salary?'")
    print("Expected: 'I could not find sufficient authorized information.'")
    
    response = generate_answer_sync("What is Neha's salary?", "engineering")
    print(f"Answer: {response.answer}")
    print(f"Citations: {[(c.source, c.page, c.row_id) for c in response.citations]}")
    print(f"Retrieved sources: {[(s.source, s.source_type, s.row_id) for s in response.retrieved_sources]}")
    
    assert "could not find sufficient authorized information" in response.answer.lower(), \
        "Should not have access to finance records"
    print("✓ PASSED\n")


def test_hr_can_access_travel_allowance():
    print("Test 3: HR user asks 'What is the travel allowance?'")
    print("Expected: ₹2,000 with PDF page citation")
    
    response = generate_answer_sync("What is the travel allowance?", "hr")
    print(f"Answer: {response.answer}")
    print(f"Citations: {[(c.source, c.page, c.row_id) for c in response.citations]}")
    print(f"Retrieved sources: {[(s.source, s.source_type, s.page) for s in response.retrieved_sources]}")
    
    assert "2000" in response.answer or "2,000" in response.answer, "Should contain travel allowance"
    assert len(response.citations) > 0, "Should have citations"
    print("✓ PASSED\n")


def test_engineering_cannot_access_travel_allowance():
    print("Test 4: Engineering user asks 'What is the travel allowance?'")
    print("Expected: 'I could not find sufficient authorized information.' (if engineering doesn't have PDF access)")
    
    response = generate_answer_sync("What is the travel allowance?", "engineering")
    print(f"Answer: {response.answer}")
    print(f"Citations: {[(c.source, c.page, c.row_id) for c in response.citations]}")
    print(f"Retrieved sources: {[(s.source, s.source_type, s.page) for s in response.retrieved_sources]}")
    
    assert "could not find sufficient authorized information" in response.answer.lower(), \
        "Engineering should not have access to HR PDF"
    print("✓ PASSED\n")


def test_unknown_information():
    print("Test 5: Ask 'What is Rahul's bonus?'")
    print("Expected: 'I could not find sufficient authorized information.'")
    
    response = generate_answer_sync("What is Rahul's bonus?", "engineering")
    print(f"Answer: {response.answer}")
    print(f"Citations: {[(c.source, c.page, c.row_id) for c in response.citations]}")
    
    assert "could not find sufficient authorized information" in response.answer.lower(), \
        "Should not hallucinate bonus information"
    print("✓ PASSED\n")


def test_unauthorized_records_not_passed_to_llm():
    print("Test 6: Verify unauthorized records are not passed to LLM")
    print("Check: Engineering user's retrieved chunks should not contain Neha (finance)")
    
    chunks = secure_search("salary", "engineering", n_results=10)
    print(f"Retrieved {len(chunks)} chunks for engineering user")
    
    for chunk in chunks:
        metadata = chunk['metadata']
        row_id = metadata.get('row_id', '')
        source = metadata.get('source', '')
        access_groups = metadata.get('access_groups', '')
        print(f"  - Source: {source}, Row: {row_id}, Access: {access_groups}")
        
        if row_id == 'E103' or 'Neha' in chunk['text']:
            raise AssertionError("Finance record E103 (Neha) was retrieved for engineering user!")
    
    print("✓ PASSED - No unauthorized records retrieved\n")


def test_admin_can_access_everything():
    print("Test 7: Admin user can access all data")
    
    response = generate_answer_sync("What is Neha's salary?", "admin")
    print(f"Answer: {response.answer}")
    print(f"Citations: {[(c.source, c.page, c.row_id) for c in response.citations]}")
    
    assert "70" in response.answer or "₹70" in response.answer, "Admin should access finance records"
    print("✓ PASSED\n")


def test_retrieval_layer_filtering():
    print("Test 8: Direct retrieval layer test - verify metadata filtering")
    
    engineering_chunks = secure_search("employee", "engineering", n_results=10)
    hr_chunks = secure_search("employee", "hr", n_results=10)
    admin_chunks = secure_search("employee", "admin", n_results=10)
    
    print(f"Engineering retrieved: {len(engineering_chunks)} chunks")
    print(f"HR retrieved: {len(hr_chunks)} chunks")
    print(f"Admin retrieved: {len(admin_chunks)} chunks")
    
    eng_sources = set()
    for chunk in engineering_chunks:
        meta = chunk['metadata']
        eng_sources.add((meta.get('source'), meta.get('row_id')))
    
    hr_sources = set()
    for chunk in hr_chunks:
        meta = chunk['metadata']
        hr_sources.add((meta.get('source'), meta.get('row_id')))
    
    admin_sources = set()
    for chunk in admin_chunks:
        meta = chunk['metadata']
        admin_sources.add((meta.get('source'), meta.get('row_id')))
    
    print(f"Engineering sources: {eng_sources}")
    print(f"HR sources: {hr_sources}")
    print(f"Admin sources: {admin_sources}")
    
    assert ('employees', 'E103') not in eng_sources, "Engineering should not see E103"
    assert ('employees', 'E103') in admin_sources, "Admin should see E103"
    assert ('company_policy.pdf', None) in hr_sources, "HR should see PDF"
    assert ('company_policy.pdf', None) not in eng_sources, "Engineering should not see PDF"
    
    print("✓ PASSED - Retrieval layer correctly filters by authorization\n")


def run_all_tests():
    setup()
    
    test_engineering_can_access_rahul_salary()
    test_engineering_cannot_access_neha_salary()
    test_hr_can_access_travel_allowance()
    test_engineering_cannot_access_travel_allowance()
    test_unknown_information()
    test_unauthorized_records_not_passed_to_llm()
    test_admin_can_access_everything()
    test_retrieval_layer_filtering()
    
    print("=" * 50)
    print("ALL TESTS PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()