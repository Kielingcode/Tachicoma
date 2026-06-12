import zlib


class CustomerRecord:
    __slots__ = ('name', 'tier',)

    def __init__(self, name, tier):
        self.name = name
        self.tier = tier


class InvoiceRecord:
    __slots__ = ('invoice_id', 'order_id', 'total_cents',)

    def __init__(self, invoice_id, order_id, total_cents):
        self.invoice_id = invoice_id
        self.order_id = order_id
        self.total_cents = total_cents


class OrderRecord:
    __slots__ = ('order_id', 'amount_cents',)

    def __init__(self, order_id, amount_cents):
        self.order_id = order_id
        self.amount_cents = amount_cents


class ShipmentRecord:
    __slots__ = ('shipment_id', 'order_id', 'carrier',)

    def __init__(self, shipment_id, order_id, carrier):
        self.shipment_id = shipment_id
        self.order_id = order_id
        self.carrier = carrier


def _pack_customer(rec):
    return {'kind': 'Customer', 'v': 3713718242, 'name': rec.name, 'tier': rec.tier}


def _pack_invoice(rec):
    return {'kind': 'Invoice', 'v': 1214547386, 'invoice_id': rec.invoice_id, 'order_id': rec.order_id, 'total_cents': rec.total_cents}


def _pack_order(rec):
    return {'kind': 'Order', 'v': 347000405, 'order_id': rec.order_id, 'amount_cents': rec.amount_cents}


def _pack_shipment(rec):
    return {'kind': 'Shipment', 'v': 3590958900, 'shipment_id': rec.shipment_id, 'order_id': rec.order_id, 'carrier': rec.carrier}


_FIELDS = {'Customer': ('name', 'tier',), 'Invoice': ('invoice_id', 'order_id', 'total_cents',), 'Order': ('order_id', 'amount_cents',), 'Shipment': ('shipment_id', 'order_id', 'carrier',)}
_SCHEMA_V = {'Customer': 3713718242, 'Invoice': 1214547386, 'Order': 347000405, 'Shipment': 3590958900}
_RECORDS = {'Customer': CustomerRecord, 'Invoice': InvoiceRecord, 'Order': OrderRecord, 'Shipment': ShipmentRecord}
_PACKERS = {'Customer': _pack_customer, 'Invoice': _pack_invoice, 'Order': _pack_order, 'Shipment': _pack_shipment}

for _k, _fs in _FIELDS.items():
    if zlib.crc32(','.join(_fs).encode()) != _SCHEMA_V[_k]:
        raise RuntimeError(
            f'record table corrupt for {_k!r} '
            f'(checksum {zlib.crc32(",".join(_fs).encode())} != {_SCHEMA_V[_k]})'
        )


def to_record(obj):
    kind = type(obj).__name__
    if kind not in _FIELDS:
        raise TypeError(f'no record type for {kind!r}')
    return _RECORDS[kind](*[getattr(obj, f) for f in _FIELDS[kind]])


def pack(rec):
    kind = type(rec).__name__[:-len('Record')]
    return _PACKERS[kind](rec)


def unpack(payload):
    kind = payload['kind']
    if payload.get('v') != _SCHEMA_V[kind]:
        raise ValueError(
            f'record schema mismatch for {kind!r}: '
            f'payload v={payload.get("v")}, expected {_SCHEMA_V[kind]}'
        )
    extra = set(payload) - {'kind', 'v', *_FIELDS[kind]}
    if extra:
        raise ValueError(f'unexpected keys in {kind!r} payload: {sorted(extra)}')
    return _RECORDS[kind](*[payload[f] for f in _FIELDS[kind]])
