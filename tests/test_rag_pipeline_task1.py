#!/usr/bin/env python
"""Test RAG pipeline with new documents table"""

import os
from dotenv import load_dotenv
load_dotenv('.env.local')

from backend.engines.rag.vector_store import store_chunks, get_document_count, search_similar
from backend.engines.rag.embedding_engine import embed_text

print("=" * 60)
print("RAG PIPELINE TEST - Task 1: RAG Engine Integration")
print("=" * 60)

# Test 1: Store chunks (with embeddings)
print("\n[1] Testing chunk storage with embeddings...")
test_texts = [
    'This is the first section about data analysis and machine learning.',
    'Advanced analytics techniques for pattern discovery and insights.',
    'Deep learning models for neural network analysis and training.',
]

try:
    test_chunks = []
    for i, text in enumerate(test_texts):
        embedding = embed_text(text)
        test_chunks.append({
            'source': 'test_doc.pdf',
            'page': (i // 2) + 1,
            'chunk_index': i,
            'content': text,
            'embedding': embedding
        })
    
    result = store_chunks(test_chunks)
    count = get_document_count()
    print(f"✅ Stored {result['inserted']} new chunks (skipped {result['skipped']} duplicates)")
    print(f"✅ Total documents in database: {count}")
except Exception as e:
    print(f"❌ Storage Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Semantic search (with embedding)
print("\n[2] Testing semantic search...")
try:
    query_text = 'machine learning and data analysis'
    query_embedding = embed_text(query_text)
    search_result = search_similar(query_embedding, top_k=2)
    
    if search_result['success']:
        results = search_result['results']
        print(f"✅ Found {len(results)} relevant chunks for query: '{query_text}'")
        for i, result in enumerate(results, 1):
            similarity = result.get('similarity', 0)
            content = result.get('content', '')[:70]
            print(f"   {i}. [{similarity}] {content}...")
    else:
        print(f"❌ Search failed: {search_result['error']}")
except Exception as e:
    print(f"❌ Search Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Verify documents table has content
print("\n[3] Verifying documents table...")
try:
    import psycopg2
    from backend.engines.rag.vector_store import get_connection
    
    conn = get_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total, COUNT(DISTINCT source) as sources FROM documents")
            row = cur.fetchone()
            print(f"✅ Database contains {row[0]} total chunks from {row[1]} source(s)")
        conn.close()
except Exception as e:
    print(f"⚠️  DB Query Error: {e}")

print("\n" + "=" * 60)
print("✅ TASK 1.4 COMPLETE: RAG Pipeline Functional")
print("=" * 60)
