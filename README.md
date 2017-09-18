# obj2svg

`obj2svg` is a command line utility to convert OBJ polygon geometry to SVG paths.

`svg2obj` is a command line utility to convert SVG paths to OBJ polygon geometry.


## Usage:

    ./obj2svg.py in.obj > out.svg
    
    ./svg2obj.py in.svg > out.obj


## Functionality

-   `obj2svg` will discard Z coordinates, compressing all geometry into the X-Y plane.
-   `svg2obj` will insert a Z coordinate of 0, generating geometry in the X-Y plane.
-   `svg2obj` will automatically adapt Bézier spline sampling. This is not currently configurable.


## Caveats

-   `svg2obj` currently only paths, not regular objects
-   `svg2obj` currently only path commands MmLlHhVvCcZz
-   `svg2obj` only processes matrix and translate transformations, ignoring rotate and scale transformations.
