MATAA_STATE_MAPPING = {
    0: 'wc-verifying',
    1: 'wc-on-hold',
    2: 'startpacking',
    3: 'kindacompleted',
    4: 'packingdone',
    5: 'processing',
    6: 'shipping',
    7: 'completed',
    8: 'failed',
    9: 'cancelled'
}

# Reverse map for syncing back
MATAA_STATE_REVERSE_MAPPING = {v: k for k, v in MATAA_STATE_MAPPING.items()}