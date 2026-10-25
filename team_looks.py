"""The Flamingos squad 2026/27 with ready-made pixel characters.

Only stylised traits (hair style, beard, glasses, colours...) are stored here,
never photos: the repository is public.
"""
from __future__ import annotations


def _look(**traits):
    base = dict(hair='corti', beard='nessuna', glasses='nessuno', brows='folte', skin='#E8B6A0', hair_color='#2E221D',
                beard_color='#6E5244', face='normale', eyes='scuri', accessory='nessuno', accessory_color='#2F4FC8',
                expression='serio', earrings=False)
    base.update(traits)
    return base


OFFICIAL_SQUAD = [
    dict(number=0, name='NICK', role='ALL', look=_look(hair='pelato', beard='piena', beard_color='#2E2420', glasses='spessi',
                                                         face='tondo', skin='#E8B49C', hair_color='#2A201C', expression='sorriso')),
    dict(number=1, name='BRAMBO', role='P', look=_look(hair='stempiato', hair_color='#2A2220', face='magro', skin='#E7B79F')),
    dict(number=12, name='OLI', role='P', look=_look(hair='corti', hair_color='#3B2E28', eyes='azzurri', beard='baffi',
                                                       beard_color='#B88A5C', skin='#F0C2A8')),
    dict(number=6, name='GIANLU', role='D', look=_look(hair='spettinati', hair_color='#1F1714', beard='corta',
                                                         beard_color='#6E5244', skin='#E2A88E')),
    dict(number=13, name='COCCO', role='D', look=_look(hair='corti', hair_color='#2A1E18', beard='corta', beard_color='#6A4A36',
                                                         accessory='cappuccio', accessory_color='#1C1A1F', skin='#E9B49A')),
    dict(number=4, name='BOBBI', role='C', look=_look(hair='corti', hair_color='#3A2A22', beard='corta', beard_color='#6A5040',
                                                        accessory='bucket', accessory_color='#2F4FC8', earrings=True, skin='#E7B9A3')),
    dict(number=14, name='DEMA', role='C', look=_look(hair='corti', hair_color='#4A382C', face='magro', brows='sottili',
                                                        skin='#F0C8B0')),
    dict(number=0, name='KEVIN', role='C', look=_look(hair='frangia', hair_color='#141012', brows='sottili', skin='#EEC6A6')),
    dict(number=3, name='LUCA', role='C', look=_look(hair='frangia', hair_color='#3E2A20', expression='sorriso', skin='#F0C6AE')),
    dict(number=10, name='CAVA', role='C', look=_look(hair='ricci_lunghi', hair_color='#4A3424', beard='corta',
                                                        beard_color='#5A4230', face='magro', skin='#EAC0A6')),
    dict(number=11, name='SCATTO', role='C', look=_look(hair='mossi', hair_color='#5A3E2C', beard='corta', beard_color='#6A4C38',
                                                          expression='sorriso', skin='#ECC0A6')),
    dict(number=8, name='ELVIN', role='C', look=_look(hair='corti', hair_color='#B89260', face='magro', eyes='azzurri',
                                                        brows='sottili', skin='#F4D2BE')),
    dict(number=15, name='STRINGA', role='C', look=_look(hair='ciuffo', hair_color='#8A6440', beard='corta', beard_color='#6A4A30',
                                                           expression='sorriso', skin='#E8B49A')),
    dict(number=5, name='TABE', role='A', look=_look(hair='ricci', hair_color='#2E2018', skin='#E6B49A')),
    dict(number=9, name='TEU', role='A', look=_look(hair='ciuffo', hair_color='#2C201B', beard='corta', beard_color='#7A5A50',
                                                      skin='#E9B39E')),
    dict(number=0, name='MANU', role='DIR', look=_look(hair='corti', glasses='sole', beard='piena', beard_color='#6A4A30',
                                                         accessory='cappellino', accessory_color='#1E1E22', face='tondo',
                                                         skin='#E4AE92')),
    dict(number=0, name='CHOPPA', role='DIR', look=_look(hair='stempiato', hair_color='#3A2C26', face='magro', skin='#EEC2A8')),
    dict(number=0, name='BANA', role='DIR', look=_look(hair='ricci', hair_color='#6E4A32', eyes='verdi', face='magro',
                                                         skin='#F2CDB6')),
]
