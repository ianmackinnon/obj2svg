#!/usr/bin/env python3

# pylint: disable=logging-too-many-args

import re
import sys
import math
import logging
import argparse
from math import atan2

import numpy as np
from bs4 import BeautifulSoup



def color_log(log):
    color_red = '\033[91m'
    color_green = '\033[92m'
    color_yellow = '\033[93m'
    color_blue = '\033[94m'
    color_end = '\033[0m'

    level_colors = (
        ("error", color_red),
        ("warning", color_yellow),
        ("info", color_green),
        ("debug", color_blue),
    )

    safe = None
    color = None

    def xor(a, b):
        return bool(a) ^ bool(b)

    def _format(value):
        if isinstance(value, float):
            return "%0.3f"
        else:
            return "%s"

    def message_args(args):
        if not args:
            return "", []
        if (
                not isinstance(args[0], str) or
                xor(len(args) > 1, "%" in args[0])
        ):
            return " ".join([_format(v) for v in args]), args
        return args[0], args[1:]

    def _message(args, color):
        message, args = message_args(args)
        return "".join([color, message, color_end])

    def _args(args):
        args = message_args(args)[1]
        return args

    def build_lambda(safe, color):
        return lambda *args, **kwargs: getattr(log, safe)(
            _message(args, color), *_args(args), **kwargs)

    for (level, color) in level_colors:
        safe = "%s_" % level
        setattr(log, safe, getattr(log, level))
        setattr(log, level, build_lambda(safe, color))



LOG = logging.getLogger("svg2obj")
color_log(LOG)



def clean_whitespace(text):
    return re.sub(r"[\s]+", " ", text).strip()



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

    a1 = atan2(p[1][1] - p[0][1], p[1][0] - p[0][0])
    a2 = atan2(p[2][1] - p[1][1], p[2][0] - p[1][0])
    a3 = atan2(p[3][1] - p[2][1], p[3][0] - p[2][0])

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



def path_to_poly(path):
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
            "length": 0,
        },
        "C": {
            "length": 6,
            "path": poly_points_bezier,
        },
    }


    poly = []
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

        if handler.get("draw", True) and not poly:
            poly.append(cursor)

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
                if handler.get("draw", True):
                    poly.append(cursor)

    # Invert Y
    poly = [(v[0], -v[1]) for v in poly]

    return poly



def transform_poly(poly, xform):
    poly2 = []
    for vertex in poly:
        v1 = np.matrix([[vertex[0]], [vertex[1]], [1]])
        v2 = xform * v1
        poly2.append([v2[0, 0], v2[1, 0]])
    return poly2



def parse_transform(text):
    text = clean_whitespace(text)

    match = re.compile(r"""
matrix\(
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+)
\)""", re.X).match(text)
    if match:
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [xform[0], xform[2], xform[4]],
            [xform[1], xform[3], xform[5]],
            [0, 0, 1]
        ))

    match = re.compile(r"""
translate\(
(-?[0-9.]+),
(-?[0-9.]+)
\)
""", re.X).match(text)
    if match:
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [1, 0, xform[0]],
            [0, 1, xform[1]],
            [0, 0, 1]
        ))

    match = re.compile(r"""
scale\(
(-?[0-9.]+),
(-?[0-9.]+)
\)
""", re.X).match(text)
    if match:
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [xform[0], 0, 0],
            [0, xform[1], 0],
            [0, 0, 1]
        ))

    match = re.compile(r"""
scale\(
(-?[0-9.]+)
\)
""", re.X).match(text)
    if match:
        xform = [float(v) for v in match.groups()]
        return np.matrix((
            [xform[0], 0, 0],
            [0, xform[0], 0],
            [0, 0, 1]
        ))

    LOG.warning(
        "No transform procedure defined for '%s'", text)



def extract_paths(node, xform=None, depth=None):
    if xform is None:
        xform = np.identity(3)
    if depth is None:
        depth = 0

    if not hasattr(node, "name") or node.name is None:
        return []

    paths = []

    if hasattr(node, "attrs") and "transform" in node.attrs:
        xform_ = parse_transform(node["transform"])
        LOG.warning(xform_)
        if xform_ is not None:
            xform = xform * xform_

    if node.name == "path":
        path = node.attrs["d"]
        poly = path_to_poly(path)
        poly = transform_poly(poly, xform)
        paths.append(poly)

    elif node.name in ["svg", "g"]:
        label = node.get("inkscape:label", None)
        if label:
            LOG.info(label)
        for child in node:
            paths += extract_paths(child, xform, depth + 1)

    elif node.name.startswith("sodipodi"):
        pass

    elif node.name in ["metadata", "defs"]:
        pass

    else:
        LOG.warning("Ignoring node: %s", node.name)


    return paths



def svg2obj(svg_file):
    """
    Use millimeters for output unit.
    """

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
        viewbox = [int(v) for v in viewbox.split()]
        unit_scale = [
            width / viewbox[2],
            height / viewbox[3]
        ]

        LOG.info("Page size (mm): %0.3f x %0.3f", width, height)
        LOG.info("View box: %0.3f %0.3f %0.3f %0.3f", *viewbox)
        LOG.info("Unit scale: %0.3f,%0.3f", *unit_scale)

        xform = np.matrix([
            [unit_scale[0], 0, 0],
            [0, unit_scale[1], 0],
            [0, 0, 1]
        ])

    paths = extract_paths(svg, xform)

    write_obj(paths)



def write_obj(paths):
    """
    Vertex numbers start from 1.
    """

    vertex_list = []
    face_list = []

    for path in paths:
        face = []
        for vertex in path:
            vertex_list.append(vertex)
            v = len(vertex_list)
            face.append(v)
        face_list.append(face)

    stream = sys.stdout

    stream.write("g\n")
    for vertex in vertex_list:
        stream.write("v %f %f 0\n" % (vertex[0], vertex[1]))
    for face in face_list:
        stream.write("f %s\n" % " ".join(["%d" % v for v in face]))
    LOG.info("Wrote %d vertices and %d faces.",
             len(vertex_list), len(face_list))



def main():
    LOG.addHandler(logging.StreamHandler())

    parser = argparse.ArgumentParser(
        description="Convert paths in an SVG file to polygons in OBJ format.")
    parser.add_argument(
        "--verbose", "-v",
        action="count", default=0,
        help="Print verbose information for debugging.")
    parser.add_argument(
        "--quiet", "-q",
        action="count", default=0,
        help="Suppress warnings.")

    parser.add_argument(
        "svg",
        metavar="SVG",
        type=argparse.FileType("r", encoding="utf-8"),
        help="Path to SVG file.")

    args = parser.parse_args()

    level = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)[
        max(0, min(3, 1 + args.verbose - args.quiet))]
    LOG.setLevel(level)

    svg2obj(args.svg)



if __name__ == "__main__":
    main()
