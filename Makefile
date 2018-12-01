SHELL := /bin/bash
.PHONY : test

all :

test : /tmp/test-triangles.obj
	diff -qs /tmp/test-triangles.obj test/test-triangles.known.obj

/tmp/test-triangles.obj : test/test-triangles.svg
	./svg2obj.py -vv $^ $@
