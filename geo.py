import re
import math
import logging

import numpy as np
from bs4 import BeautifulSoup

from common import clean_whitespace



LOG = logging.getLogger("geo")



def text_to_mm(text):
    text = text.strip().lower()

    match = re.compile(r"^([0-9.]+)\s*mm$", re.U).match(text)
    if match:
        return float(match.group(1))

    match = re.compile(r"^([0-9.]+)\s*cm$", re.U).match(text)
    if match:
        return float(match.group(1)) * 10

    match = re.compile(r"^([0-9.]+)\s*in$", re.U).match(text)
    if match:
        return float(match.group(1)) * 25.4

    LOG.error(
        "No conversion to millimeters found for '%s'.",
        text
    )

    return None



def transform_poly(poly, xform):
    poly2 = []
    for vertex in poly:
        v1 = np.matrix([[vertex[0]], [vertex[1]], [1]])
        v2 = xform * v1
        poly2.append([v2[0, 0], v2[1, 0]])
    return poly2



def poly_points_bezier(_command, cursor, segment, absolute):
    """
    Return absolute points
    """

    vertex_list = [tuple(cursor)]
    while segment:
        vertex = tuple(segment[:2])
        segment = segment[2:]

        if absolute:
            vertex_list.append(tuple(vertex))
        else:
            vertex_list.append((
                cursor[0] + vertex[0],
                cursor[1] + vertex[1]
            ))

    def point(p0, p1, p2, p3, t):
        return (
            p0 * pow((1 - t), 3) +
            p1 * 3 * pow((1 - t), 2) * t +
            p2 * 3 * (1 - t) * pow(t, 2) +
            p3 * pow(t, 3)
        )

    def ang_diff(a1, a2):
        diff = a2 - a1
        if diff > math.pi:
            diff -= 2 * math.pi
        if diff < -math.pi:
            diff += 2 * math.pi
        return diff

    p = vertex_list

    a1 = math.atan2(p[1][1] - p[0][1], p[1][0] - p[0][0])
    a2 = math.atan2(p[2][1] - p[1][1], p[2][0] - p[1][0])
    a3 = math.atan2(p[3][1] - p[2][1], p[3][0] - p[2][0])

    d1 = ang_diff(a1, a2)
    d2 = ang_diff(a2, a3)
    dx = p[3][0] - p[0][0]
    dy = p[3][1] - p[0][1]

    length = math.sqrt(dx * dx + dy * dy)
    d = abs(d1) + abs(d2)

    vertex_list = []
    n = 1 + int(10 * d) +  int(length / 100)
    for i in range(n):
        t = float(i + 1) / n
        x = point(p[0][0], p[1][0], p[2][0], p[3][0], t)
        y = point(p[0][1], p[1][1], p[2][1], p[3][1], t)
        vertex_list.append((x, y))

    return vertex_list



def poly_points_linear(command, cursor, segment, absolute):
    """
    Return absolute points
    """

    if command.upper() == "H":
        segment.insert(1, cursor[1] if absolute else 0)
    if command.upper() == "V":
        segment.insert(0, cursor[0] if absolute else 0)

    if absolute:
        return [list(segment)]

    return [[
        cursor[0] + segment[0],
        cursor[1] + segment[1],
    ]]



def path_to_poly_list(path):
    path = " " + clean_whitespace(path)
    path = re.compile(" ([mlhvzcsqta])([0-9-])", re.I).sub(r"\1 \2", path)
    path = re.sub(",", " ", path)

    handlers = {
        "M": {
            "length": 2,
            "draw": False,
            "path": poly_points_linear,
        },
        "L": {
            "length": 2,
            "path": poly_points_linear,
        },
        "H": {
            "length": 1,
            "path": poly_points_linear,
        },
        "V": {
            "length": 1,
            "path": poly_points_linear,
        },
        "Z": {
            "length": 0
        },
        "C": {
            "length": 6,
            "path": poly_points_bezier,
        },
    }


    poly_list = [[]]
    cursor = [0, 0]
    command_list = re.compile(" ([mlhvzcsqta])", re.I).split(path)[1:]
    for i in range(0, len(command_list), 2):
        command = command_list[i]
        absolute = command == command.upper()
        values = clean_whitespace(command_list[i + 1]).split()

        try:
            handler = handlers[command.upper()]
        except KeyError:
            LOG.error("No handler for path segment: %s %s",
                      command, values)
            break

        try:
            values = [float(v) for v in values]
        except ValueError:
            LOG.error("Could not convert all values to float: %s",
                      values)
            break

        if handler.get("draw", True) is False:
            if poly_list[-1]:
                poly_list.append([])

        while values:
            segment = values[:handler["length"]]
            values = values[handler["length"]:]
            if "value" in handler:
                segment = handler["value"](segment)

            if not "path" in handler:
                break

            vertex_list = handler["path"](
                command, cursor, segment, absolute)

            for vertex in vertex_list:
                cursor = list(vertex)
                poly_list[-1].append(cursor)

        if command.upper() == "Z":
            poly_list[-1].append(poly_list[-1][0])


    poly_list = [[(v[0], v[1]) for v in poly] for poly in poly_list]

    return poly_list



def parse_transform(text):
    text = clean_whitespace(text)

    match = re.compile(r"""
matrix\(
([0-9.e-]+),
([0-9.e-]+),
([0-9.e-]+),
([0-9.e-]+),
([0-9.e-]+),
([0-9.e-]+)
\)""", re.X).match(text)
    if match:
        LOG.debug("transform: %s" % match.group(0))
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [xform[0], xform[2], xform[4]],
            [xform[1], xform[3], xform[5]],
            [0, 0, 1]
        ))

    match = re.compile(r"""
translate\(
([0-9.e-]+),
([0-9.e-]+)
\)
""", re.X).match(text)
    if match:
        LOG.debug("transform: %s" % match.group(0))
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [1, 0, xform[0]],
            [0, 1, xform[1]],
            [0, 0, 1]
        ))

    match = re.compile(r"""
translate\(
([0-9.e-]+)
\)
""", re.X).match(text)
    if match:
        LOG.debug("transform: %s" % match.group(0))
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [1, 0, xform[0]],
            [0, 1, 0],
            [0, 0, 1]
        ))

    match = re.compile(r"""
rotate\(
([0-9.e-]+)
\)
""", re.X).match(text)
    if match:
        LOG.debug("transform: %s" % match.group(0))
        xform = [float(v) for v in match.groups()]
        theta = math.radians(xform[0])
        return np.matrix((
            [math.cos(theta), math.sin(theta), 0],
            [-math.sin(theta), math.cos(theta), 0],
            [0, 0, 1]
        ))

    match = re.compile(r"""
rotate\(
([0-9.e-]+),
([0-9.e-]+),
([0-9.e-]+)
\)
""", re.X).match(text)
    if match:
        LOG.debug("transform: %s" % match.group(0))
        xform = [float(v) for v in match.groups()]
        theta = math.radians(xform[0])
        return np.matrix((
            [1, 0, xform[1]],
            [0, 1, xform[2]],
            [0, 0, 1]
        )) * np.matrix((
            [math.cos(theta), math.sin(theta), 0],
            [-math.sin(theta), math.cos(theta), 0],
            [0, 0, 1]
        )) * np.matrix((
            [1, 0, -xform[1]],
            [0, 1, -xform[2]],
            [0, 0, 1]
        ))

    match = re.compile(r"""
scale\(
([0-9.e-]+),
([0-9.e-]+)
\)
""", re.X).match(text)
    if match:
        LOG.debug("transform: %s" % match.group(0))
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [xform[0], 0, 0],
            [0, xform[1], 0],
            [0, 0, 1]
        ))

    match = re.compile(r"""
scale\(
([0-9.e-]+)
\)
""", re.X).match(text)
    if match:
        LOG.debug("transform: %s" % match.group(0))
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [xform[0], 0, 0],
            [0, xform[0], 0],
            [0, 0, 1]
        ))

    LOG.warning(
        "No transform procedure defined for '%s'", text)

    return None



def extract_paths(node, xform=None, depth=None):
    if xform is None:
        xform = np.identity(3)
    if depth is None:
        depth = 0

    if not hasattr(node, "name") or node.name is None:
        return []

    paths = []

    if hasattr(node, "attrs") and "transform" in node.attrs:
        LOG.debug("transform raw: %s %s", node.name, node["transform"])
        xform_ = parse_transform(node["transform"])
        if xform_ is not None:
            xform = xform * xform_

    if node.name == "path":
        path = node.attrs["d"]
        poly_list = path_to_poly_list(path)
        poly_list = [transform_poly(poly, xform) for poly in poly_list]
        paths += poly_list

    elif node.name in ["svg", "g"]:
        label = node.get("inkscape:label", None)
        style = node.get("style", "")
        if "display:none" not in style:
            if label:
                LOG.info(label)
            for child in node:
                paths += extract_paths(child, np.copy(xform), depth + 1)
        else:
            if label:
                LOG.debug(label)


    elif node.name.startswith("sodipodi"):
        pass

    elif node.name in ["metadata", "defs"]:
        pass

    else:
        LOG.warning("Ignoring node: %s", node.name)

    return paths



def svg2paths(svg_file):
    LOG.info("Converting %s", svg_file.name)

    svg_text = svg_file.read()

    soup = BeautifulSoup(svg_text, "lxml")

    svg = soup.find("svg")
    xform = None

    width = svg.get("width", None)
    height = svg.get("height", None)
    viewbox = svg.get("viewbox", None)

    if width and height and viewbox:
        width = text_to_mm(width)
        height = text_to_mm(height)
        viewbox = [float(v) for v in viewbox.split()]
        unit_scale = [
            width / viewbox[2],
            height / viewbox[3]
        ]

        LOG.info("Page size (mm): %0.3f x %0.3f", width, height)
        LOG.info("View box: %0.3f %0.3f %0.3f %0.3f", *viewbox)
        LOG.info("Unit scale: %0.3f, %0.3f", *unit_scale)

        xform = np.matrix([
            [unit_scale[0], 0, 0],
            [0, -unit_scale[1], height],
            [0, 0, 1]
        ])

    paths = extract_paths(svg, xform)

    return paths
