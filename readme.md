# obj2svg

`obj2svg` is a command line utility to convert OBJ polygon geometry to SVG paths.

`svg2obj` is a command line utility to convert SVG paths to OBJ polygon geometry.

`svg2gcode` is a command line utility to convert SVG paths to G-code plotter toolpaths.


## Usage:

    ./obj2svg.py in.obj > out.svg
    
    ./svg2obj.py in.svg > out.obj, or
    ./svg2obj.py in.svg out.obj

    ./svg2gcode.py in.svg > out.gcode, or
    ./svg2gcode.py in.svg out.gcode


## Functionality

-   `obj2svg` will discard Z coordinates, compressing all geometry into the X-Y plane.
-   `svg2*` will insert a Z coordinate of 0, generating geometry in the X-Y plane.
-   `svg2*` will automatically adapt Bézier spline sampling. This is not currently configurable.


## Caveats

-   `svg2*` currently only paths, not regular objects
-   `svg2*` currently only path commands MmLlHhVvCcZz
