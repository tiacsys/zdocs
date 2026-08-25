# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0
#
# Included by the Zephyr build system when zdocs is loaded as a module in a full
# application build. It deliberately does NOT wire the engine up: consumers enter
# a documentation build directly (cmake -S doc) through
# `find_package(Zephyr COMPONENTS doc)`, a reduced flow in which this file is not
# reliably executed. The supported entry point is:
#
#   list(APPEND CMAKE_MODULE_PATH ${ZEPHYR_ZDOCS_MODULE_DIR}/cmake)
#   include(zdocs)
#
# Anything put here would work in an application build and silently not in a doc
# build, which is the confusing half of that asymmetry.
message(STATUS "zdocs module present (engine entry point: cmake/zdocs.cmake)")
