def row_to_dict(row, exclude=None):
    """SQLAlchemy model instance to JSON-serializable dict."""
    exclude = set(exclude or [])
    d = {}
    for c in row.__table__.columns:
        if c.name in exclude:
            continue
        v = getattr(row, c.name)
        if hasattr(v, "isoformat"):
            d[c.name] = v.isoformat() if v is not None else None
        elif hasattr(v, "hex"):
            d[c.name] = str(v)
        else:
            d[c.name] = v
    return d
