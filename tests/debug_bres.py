def _has_clear_extended_los(x0, y0, x1, y1):
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x = x0
    y = y0

    print(f"start: dx={dx}, dy={dy}, err={err}")
    while x != x1 or y != y1:
        twice_err = 2 * err
        print(f"loop start: x={x}, y={y}, twice_err={twice_err}")
        if twice_err > -dy:
            err -= dy
            x += sx
            print(f"  step X: err={err}, x={x}")
        if twice_err < dx:
            err += dx
            y += sy
            print(f"  step Y: err={err}, y={y}")

        if x == x1 and y == y1:
            print("  reached target")
            return True
        print(f"  check block at x={x}, y={y}")

_has_clear_extended_los(2, 19, 4, 19)
