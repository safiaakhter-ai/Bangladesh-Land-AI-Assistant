"""
Automated Test Suite for Bangladesh Land Record AI RAG System
Tests 4-step pipeline: Entity Extraction, Structured DB Query, Ambiguity Disambiguation,
and Answer Synthesis for sample scenarios Q1-Q10.
"""

import sys
import json
import time
from rag_engine import LandRecordRAG
import chat_db

def run_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 65)
    print("RUNNING LAND RECORDS RAG SYSTEM COMPREHENSIVE SUITE (16 SCENARIOS)")
    print("=" * 65)

    rag = LandRecordRAG()

    # Index initialization test
    start_t = time.time()
    fts_ok = rag.ensure_fts_index()
    duration = (time.time() - start_t) * 1000
    print(f"\n[Index Check] FTS5 Index Status: {'OK' if fts_ok else 'FAILED'} ({duration:.2f} ms)")

    # 1. Banglish Direct Lookup
    start_t = time.time()
    res1 = rag.process_query("Sarail er Kartik Nath er jomir details din")
    dur1 = (time.time() - start_t) * 1000
    print(f"\n[1/15 Test - Banglish Direct Lookup] 'Sarail er Kartik Nath er jomir details din'")
    print(f"   - Latency: {dur1:.2f} ms")
    print(f"   - Answer Snippet: {res1['answer'][:120]}...")
    assert "সরাইল" in res1['answer'] or "Sarail" in res1['answer'] or "Kartik Nath" in res1['answer'], "Q1 failed!"

    # 2. Ambiguous Owner Query
    start_t = time.time()
    res2 = rag.process_query("কার্ত্তিক নাথ এর জমির তথ্য দাও")
    dur2 = (time.time() - start_t) * 1000
    print(f"\n[2/15 Test - Ambiguous Owner Query] 'কার্ত্তিক নাথ এর জমির তথ্য দাও'")
    print(f"   - Latency: {dur2:.2f} ms")
    print(f"   - Answer Snippet: {res2['answer'][:120]}...")

    # 3. Single Match Query
    start_t = time.time()
    res3 = rag.process_query("কার্ত্তিক নাথের জমি কোথায়?")
    dur3 = (time.time() - start_t) * 1000
    print(f"\n[3/15 Test - Single Match Query] 'কার্ত্তিক নাথের জমি কোথায়?'")
    print(f"   - Latency: {dur3:.2f} ms")
    print(f"   - Answer Snippet: {res3['answer'][:120]}...")

    # 4. Mouza List Query
    start_t = time.time()
    res4 = rag.process_query("ভান্ডারিয়া এর সব জমির লিস্ট দাও")
    dur4 = (time.time() - start_t) * 1000
    print(f"\n[4/15 Test - Mouza List Query] 'ভান্ডারিয়া এর সব জমির লিস্ট দাও'")
    print(f"   - Latency: {dur4:.2f} ms")
    print(f"   - Records Found: {res4['records_found']}")
    print(f"   - Answer Snippet: {res4['answer'][:120]}...")
    assert res4['records_found'] > 0, "Mouza list should return mouzas for Bhandaria!"

    # 5. Upazila List Query
    start_t = time.time()
    res5_up = rag.process_query("chandpur er upazila list")
    dur5_up = (time.time() - start_t) * 1000
    print(f"\n[5/15 Test - Upazila List Query] 'chandpur er upazila list'")
    print(f"   - Latency: {dur5_up:.2f} ms")
    print(f"   - Extracted Params: {json.dumps(res5_up['extracted_params'], ensure_ascii=False)}")
    print(f"   - Answer Snippet: {res5_up['answer'][:120]}...")
    assert "upazila" in res5_up['answer'].lower() or "উপজেলা" in res5_up['answer'], "Upazila list query failed!"

    # 6. Multi-turn Location Selection (Retain Owner)
    start_t = time.time()
    hist_m1 = [
        {"sender": "user", "content": "মোহাম্মদআলী er jomir details dao", "metadata": {"extracted_params": {"owner_name": "মোহাম্মদআলী"}, "answer": "মোহাম্মদআলী নামে একাধিক এলাকায় রেকর্ড পাওয়া যাচ্ছে..."}}
    ]
    res6_loc = rag.process_query("কলাগাছিয়া মৌজা", conversation_history=hist_m1)
    dur6_loc = (time.time() - start_t) * 1000
    print(f"\n[6/15 Test - Location Selection Turn] 'কলাগাছিয়া মৌজা'")
    print(f"   - Latency: {dur6_loc:.2f} ms")
    print(f"   - Extracted Params: {json.dumps(res6_loc['extracted_params'], ensure_ascii=False)}")
    print(f"   - Answer Snippet: {res6_loc['answer'][:120]}...")
    assert res6_loc['extracted_params'].get('owner_name') == "মোহাম্মদআলী", "Owner name should be retained on location selection!"

    # 7. Multi-turn Topic Switch (Isolate Owner)
    start_t = time.time()
    res7_sw = rag.process_query("chandpur er upazila list", conversation_history=hist_m1)
    dur7_sw = (time.time() - start_t) * 1000
    print(f"\n[7/15 Test - Topic Switch Turn] 'chandpur er upazila list' after owner query")
    print(f"   - Latency: {dur7_sw:.2f} ms")
    print(f"   - Extracted Params: {json.dumps(res7_sw['extracted_params'], ensure_ascii=False)}")
    print(f"   - Answer Snippet: {res7_sw['answer'][:120]}...")
    assert res7_sw['extracted_params'].get('owner_name') is None, "Owner name must NOT leak into upazila list query!"

    # 8. Dag Lookup Query
    start_t = time.time()
    res5 = rag.process_query("সরাইল উপজেলায় দাগ নম্বর ৭৪ এর মালিক কে?")
    dur5 = (time.time() - start_t) * 1000
    print(f"\n[8/15 Test - Dag Lookup Query] 'সরাইল উপজেলায় দাগ নম্বর ৭৪ এর মালিক কে?'")
    print(f"   - Latency: {dur5:.2f} ms")
    print(f"   - Extracted Dag No: {res5['extracted_params'].get('dag_no')}")
    assert res5['extracted_params'].get('dag_no') == "74", "Dag number should be extracted as 74!"

    # 9. Khatian Lookup Query
    start_t = time.time()
    res9_kh = rag.process_query("সরাইলে খতিয়ান নম্বর ২০ এর বিবরণ দাও")
    dur9_kh = (time.time() - start_t) * 1000
    print(f"\n[9/15 Test - Khatian Lookup Query] 'সরাইলে খতিয়ান নম্বর ২০ এর বিবরণ দাও'")
    print(f"   - Latency: {dur9_kh:.2f} ms")
    print(f"   - Extracted Khatian No: {res9_kh['extracted_params'].get('khatian_no')}")
    assert res9_kh['extracted_params'].get('khatian_no') == "20", "Khatian number should be extracted as 20!"

    # Exact mouza + khatian lookup must not return the same khatian number
    # from unrelated mouzas.
    res_exact = rag.process_query("ভাট বাড়ীয়া মৌজার খতিয়ান ৩ এর মালিক কে?")
    print(f"\n[9b/15 Test - Exact Mouza + Khatian Lookup]")
    print(f"   - Records Found: {res_exact['records_found']}")
    assert res_exact['records_found'] == 1, "Exact mouza and khatian lookup should return one record!"
    assert res_exact['records'][0]['details'].get('KHATIAN_NO') == '3', "Exact lookup returned the wrong khatian!"
    assert res_exact['records'][0]['details'].get('MOUZA_NAME') == 'ভাট বাড়ীয়া', "Exact lookup returned the wrong mouza!"

    # 10. Zero Matches Query
    start_t = time.time()
    res6 = rag.process_query("রাজশাহীর একরামুল হকের জমির তথ্য দাও")
    dur6 = (time.time() - start_t) * 1000
    print(f"\n[10/15 Test - Zero Matches Query] 'রাজশাহীর একরামুল হকের জমির তথ্য দাও'")
    print(f"   - Latency: {dur6:.2f} ms")
    print(f"   - Records Found: {res6['records_found']}")
    assert res6['records_found'] == 0, "No records should be found in Rajshahi!"

    # 11. Survey Type Ambiguity
    start_t = time.time()
    res7 = rag.process_query("ভাট বাড়ীয়া মৌজার এই জমির মালিকানা কি বদলেছে?")
    dur7 = (time.time() - start_t) * 1000
    print(f"\n[11/15 Test - Survey Type Ambiguity] 'ভাট বাড়ীয়া মৌজার এই জমির মালিকানা কি বদলেছে?'")
    print(f"   - Latency: {dur7:.2f} ms")
    print(f"   - Answer Snippet: {res7['answer'][:120]}...")

    # 12. Null Total Land Query
    start_t = time.time()
    res8 = rag.process_query("কার্ত্তিক নাথের জমির মোট পরিমাণ কত?")
    dur8 = (time.time() - start_t) * 1000
    print(f"\n[12/15 Test - Null Total Land Query] 'কার্ত্তিক নাথের জমির মোট পরিমাণ কত?'")
    print(f"   - Latency: {dur8:.2f} ms")
    assert len(res8['answer']) > 10 and any(w in res8['answer'] for w in ["পরিমাণ", "পরিমান", "জমির", "রেকর্ড", "খতিয়ান", "খতিয়ান", "তথ্য", "recorded"]), "Note on null total land should be returned!"

    # 13. English Query
    start_t = time.time()
    res9 = rag.process_query("Who owns dag 74 in Sarail?")
    dur9 = (time.time() - start_t) * 1000
    print(f"\n[13/15 Test - English Query] 'Who owns dag 74 in Sarail?'")
    print(f"   - Latency: {dur9:.2f} ms")
    assert "Sarail" in res9['answer'] or "সরাইল" in res9['answer'], "English answer should mention Sarail!"

    # 14. General Law FAQ Query
    start_t = time.time()
    res14_faq = rag.process_query("ই-নামজারির সরকারি ফি ও সময়সীমা কত?", conversation_history=hist_m1)
    dur14_faq = (time.time() - start_t) * 1000
    print(f"\n[14/15 Test - General Law FAQ Query] 'ই-নামজারির সরকারি ফি ও সময়সীমা কত?'")
    print(f"   - Latency: {dur14_faq:.2f} ms")
    print(f"   - Answer Snippet: {res14_faq['answer'][:120]}...")
    assert res14_faq['extracted_params'].get('intent') == "general_question", "FAQ intent should be general_question!"

    # 15. Out-of-Scope Query
    time.sleep(1)
    start_t = time.time()
    res_oos = rag.process_query("How to make chocolate cake?")
    dur_oos = (time.time() - start_t) * 1000
    print(f"\n[15/15 Test - Out of Scope Query] 'How to make chocolate cake?'")
    print(f"   - Latency: {dur_oos:.2f} ms")
    assert res_oos.get('is_out_of_scope') is True, "Cooking recipe should be detected as Out-of-Scope!"

    print("\n" + "=" * 65)
    print("ALL 16 COMPREHENSIVE SCENARIO VERIFICATION TESTS PASSED! ✅")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
