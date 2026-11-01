from src.agent import resources


def test_common_hinglish_clothing_noun_resolves_to_catalog_category():
    policy=resources().policy
    for word in ['kapde','kapdo','kapdon','kapade','kappde']:
        assert policy._category('Mujhe '+word+' return karne hain')=='fashion'
    assert policy._category('Mera net banking refund kab aayega?') is None
