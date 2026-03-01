#!/usr/bin/env python3
"""
Test script to verify the KnowledgeGraphBuilder fix.
"""
import sys
sys.path.insert(0, '.')

try:
    from chattutor.core.kg_builder import KnowledgeGraphBuilder
    print("✓ Successfully imported KnowledgeGraphBuilder")

    # Test instantiation with defaults
    builder = KnowledgeGraphBuilder()
    print("✓ Created KnowledgeGraphBuilder instance")

    # Check that the missing attributes exist
    required_attrs = [
        'enable_semantic_normalization',
        'enable_transitive_reduction',
        'enable_lpg_transformation',
        'enable_statistical_filtering',
        'semantic_similarity_threshold',
        'transitive_reduction_threshold',
        'statistical_filtering_threshold',
        'entropy_filtering_threshold'
    ]

    for attr in required_attrs:
        if hasattr(builder, attr):
            print(f"✓ Attribute '{attr}' exists: {getattr(builder, attr)}")
        else:
            print(f"✗ Attribute '{attr}' MISSING!")
            sys.exit(1)

    # Test with a small text (should not crash due to missing attributes)
    test_text = "清华大学位于北京。北京是中国的首都。"
    print(f"\nTesting build_graph with sample text: '{test_text}'")

    # Note: This may fail due to missing models, but attribute errors should be gone
    try:
        stats = builder.build_graph(test_text)
        print(f"✓ build_graph completed (no attribute errors)")
        print(f"  Entity count: {stats.get('entity_count', 'N/A')}")
        print(f"  Relation count: {stats.get('relation_count', 'N/A')}")
    except AttributeError as e:
        print(f"✗ AttributeError during build_graph: {e}")
        sys.exit(1)
    except Exception as e:
        # Other exceptions (e.g., missing models) are okay for this test
        print(f"  Other exception (expected if models not installed): {type(e).__name__}: {e}")

    print("\n✅ All attribute checks passed!")

except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)