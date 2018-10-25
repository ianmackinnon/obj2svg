SHELL := /bin/bash

all :

test : /tmp/test-triangles.obj

/tmp/test-triangles.obj : test/test-triangles.svg
	./svg2obj.py -vv $^ $@
