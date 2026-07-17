# -*- mode: python ; coding: utf-8 -*-
import os
import sqlite_vec


_sqlite_vec_dir = os.path.dirname(sqlite_vec.__file__)
_sqlite_vec_dll = os.path.join(_sqlite_vec_dir, "vec0.dll")

a = Analysis(
    ['mcat.py'],
    pathex=[],
    binaries=[(_sqlite_vec_dll, 'sqlite_vec')] if os.path.exists(_sqlite_vec_dll) else [],
    datas=[],
    hiddenimports=['winreg', 'sqlite_vec', 'pdfplumber', 'pdfminer', 'pdfminer.high_level', 'pdfminer.pdfinterp', 'pdfminer.converter', 'pdfminer.layout', 'pdfminer.pdfpage', 'pypdf', 'reportlab', 'reportlab.lib.pagesizes', 'reportlab.pdfgen', 'docx', 'pptx', 'openpyxl', 'xlrd', 'odf', 'odf.opendocument', 'odf.text', 'odf.table', 'odf.element', 'translate', 'translate.storage', 'translate.storage.po', 'translate.storage.factory', 'rapidfuzz', 'sqlite3', 'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui', 'spylls', 'spylls.hunspell', 'spylls.hunspell.readers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tensorflow', 'torch', 'scipy', 'matplotlib', 'pandas', 'numba', 'llvmlite', 'sqlalchemy', 'notebook', 'jupyter', 'ipython', 'flask', 'django', 'selenium', 'sklearn', 'cv2', 'nltk', 'gensim', 'spacy', 'seaborn', 'networkx', 'sympy', 'statsmodels', 'kivy', 'pygame', 'tornado', 'sphinx', 'nose', 'rope', 'autopep8', 'mypy', 'black', 'pylint'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mcat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='mcat',
)
