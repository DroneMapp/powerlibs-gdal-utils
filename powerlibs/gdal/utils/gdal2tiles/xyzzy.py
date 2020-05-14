class Xyzzy:
    """Collection of coordinates describing what to read and where
       for the given tile at the base level."""

    def __init__(
        self, querysize, rx, ry, rxsize, rysize, wx, wy, wxsize, wysize
    ):
        # TODO: use a proper data structure, here...
        self.querysize = querysize
        self.rx = rx
        self.ry = ry
        self.rxsize = rxsize
        self.rysize = rysize
        self.wx = wx
        self.wy = wy
        self.wxsize = wxsize
        self.wysize = wysize
