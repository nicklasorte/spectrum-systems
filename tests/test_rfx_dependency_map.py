from spectrum_systems.modules.runtime.rfx_dependency_map import build_rfx_dependency_map


def test_rt_h06_hidden_dependency_blocked_then_revalidate():
    bad=build_rfx_dependency_map(modules=[{'module':'a','produces':['x'],'consumes':['y'],'depends_on_modules':['ghost'],'owner_refs':['EVL']}])
    assert 'rfx_hidden_dependency_detected' in bad['reason_codes_emitted']
    good=build_rfx_dependency_map(modules=[{'module':'a','produces':['x'],'consumes':[],'depends_on_modules':[],'owner_refs':['EVL']},{'module':'b','produces':['y'],'consumes':['x'],'depends_on_modules':['a'],'owner_refs':['FRE']}])
    assert 'rfx_hidden_dependency_detected' not in good['reason_codes_emitted']
