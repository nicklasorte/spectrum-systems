from spectrum_systems.modules.runtime.rfx_trend_clustering_hardening import cluster_rfx_reason_codes


def test_rt_h08_variant_split_cluster_or_ambiguity_then_revalidate():
    bad=cluster_rfx_reason_codes(reasons=['abc_v1','abc_v2'])
    assert ('rfx_reason_variant_clustered' in bad['reason_codes_emitted']) or ('rfx_reason_cluster_ambiguous' in bad['reason_codes_emitted'])
    good=cluster_rfx_reason_codes(reasons=['abc_v1','abc_v2'],alias_map={'abc_v1':'abc','abc_v2':'abc'})
    assert 'abc' in good['clusters']
