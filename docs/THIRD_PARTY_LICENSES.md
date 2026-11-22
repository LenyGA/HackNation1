# Licencje komponentów zewnętrznych (5.3)

Lista wygenerowana automatycznie 22.11.2026 z zainstalowanych pakietów backendu (`backend/.venv`, wersje z
`backend/requirements*.txt`) i z `frontend/package-lock.json` (licencja z `package.json` pakietu). Obejmuje zależności
pośrednie. Źródłem każdej biblioteki jest publiczny rejestr PyPI lub npm (link w tabeli). Kod aplikacji: © 2026 GeoSatel, wszelkie prawa zastrzeżone (`LICENSE`).
Opis licencji danych, usług i narzędzi AI: `README.md`, rozdz. 6–7.

## Podsumowanie

- Backend, w aplikacji (74 pakietów): Apache Software License (26), MIT (15), BSD-3-Clause (13), BSD License (7), MIT License (4), Apache-2.0 (2), PSF-2.0 (1), BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (1), GNU General Public License v2 or later (GPLv2+), GNU Lesser General Public License v2 or later (LGPLv2+), Mozilla Public License 1.1 (MPL 1.1) (1), Mozilla Public License 2.0 (MPL 2.0) (1), MIT-CMU (1), Apache Software License, MIT License (1), MIT-0 (1)
- Backend, tylko do testów i jakości (15): MIT (7), Apache-2.0 (3), BSD License (1), Mozilla Public License 2.0 (MPL 2.0) (1), BSD-2-Clause (1), Apache-2.0 OR BSD-2-Clause (1), MIT License (1)
- Frontend, zależności produkcyjne (`dependencies` i ich zależności; część, np. Tailwind z lightningcss na MPL-2.0, działa tylko przy budowaniu, a do przeglądarki trafia sam wynikowy CSS) (195): MIT (161), MPL-2.0 (12), ISC (10), BSD-3-Clause (4), BSD-2-Clause (2), 0BSD (2), Apache-2.0 (2), (MIT OR Apache-2.0) (1), BlueOak-1.0.0 (1)
- Frontend, tylko do budowania i testów (148): MIT (114), Apache-2.0 (15), ISC (9), BSD-2-Clause (6), BlueOak-1.0.0 (2), CC-BY-4.0 (1), BSD-3-Clause (1)

Żaden komponent nie jest na licencji GPL ani AGPL bez możliwości wyboru innej licencji. Pozycja „GPLv2+, LGPLv2+, MPL 1.1”
w podsumowaniu to jeden pakiet, pyphen (dzielenie wyrazów w WeasyPrint), z licencją do wyboru: używamy go na MPL-1.1.
Pakiety oznaczone `?` nie podają licencji w metadanych; ich licencja jest w repozytorium źródłowym (link).

## Backend (Python): w aplikacji

| Pakiet | Wersja | Licencja | Źródło |
|---|---|---|---|
| affine | 3.0.1 | BSD-3-Clause | https://pypi.org/project/affine/ |
| annotated-doc | 0.0.7 | MIT | https://pypi.org/project/annotated-doc/ |
| annotated-types | 0.8.0 | MIT | https://pypi.org/project/annotated-types/ |
| anyio | 4.16.0 | MIT | https://pypi.org/project/anyio/ |
| attrs | 26.1.0 | MIT | https://pypi.org/project/attrs/ |
| certifi | 2026.11.20 | Mozilla Public License 2.0 (MPL 2.0) | https://pypi.org/project/certifi/ |
| cffi | 2.1.1 | MIT-0 | https://pypi.org/project/cffi/ |
| charset-normalizer | 3.5.2 | MIT | https://pypi.org/project/charset-normalizer/ |
| click | 8.5.1 | BSD-3-Clause | https://pypi.org/project/click/ |
| cssselect2 | 0.10.1 | BSD License | https://pypi.org/project/cssselect2/ |
| fastapi | 0.165.0 | MIT | https://pypi.org/project/fastapi/ |
| fonttools | 4.68.0 | MIT | https://pypi.org/project/fonttools/ |
| h11 | 0.16.0 | MIT License | https://pypi.org/project/h11/ |
| httpcore | 1.0.9 | BSD-3-Clause | https://pypi.org/project/httpcore/ |
| httptools | 0.9.0 | MIT | https://pypi.org/project/httptools/ |
| httpx | 0.28.1 | BSD License | https://pypi.org/project/httpx/ |
| idna | 3.20 | BSD-3-Clause | https://pypi.org/project/idna/ |
| Jinja2 | 3.1.6 | BSD License | https://pypi.org/project/Jinja2/ |
| MarkupSafe | 3.0.4 | BSD-3-Clause | https://pypi.org/project/MarkupSafe/ |
| numpy | 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://pypi.org/project/numpy/ |
| opentelemetry-api | 1.45.2 | Apache-2.0 | https://pypi.org/project/opentelemetry-api/ |
| pillow | 13.0.0 | MIT-CMU | https://pypi.org/project/pillow/ |
| pycparser | 3.12 | BSD-3-Clause | https://pypi.org/project/pycparser/ |
| pydantic | 2.14.4 | MIT | https://pypi.org/project/pydantic/ |
| pydantic_core | 2.50.5 | MIT | https://pypi.org/project/pydantic_core/ |
| pydantic-settings | 2.16.3 | MIT | https://pypi.org/project/pydantic-settings/ |
| pydyf | 0.13.0 | BSD License | https://pypi.org/project/pydyf/ |
| pyparsing | 3.3.3 | MIT | https://pypi.org/project/pyparsing/ |
| pyphen | 0.18.1 | GNU General Public License v2 or later (GPLv2+), GNU Lesser General Public License v2 or later (LGPLv2+), Mozilla Public License 1.1 (MPL 1.1) | https://pypi.org/project/pyphen/ |
| pyproj | 3.8.0 | MIT | https://pypi.org/project/pyproj/ |
| pystac | 1.16.1 | Apache Software License | https://pypi.org/project/pystac/ |
| pystac-client | 0.9.1 | Apache Software License | https://pypi.org/project/pystac-client/ |
| pystac-core | 1.16.1 | Apache Software License | https://pypi.org/project/pystac-core/ |
| pystac-ext-classification | 2.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-classification/ |
| pystac-ext-datacube | 2.2.2 | Apache Software License | https://pypi.org/project/pystac-ext-datacube/ |
| pystac-ext-eo | 1.1.2 | Apache Software License | https://pypi.org/project/pystac-ext-eo/ |
| pystac-ext-file | 2.1.2 | Apache Software License | https://pypi.org/project/pystac-ext-file/ |
| pystac-ext-grid | 1.1.2 | Apache Software License | https://pypi.org/project/pystac-ext-grid/ |
| pystac-ext-item-assets | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-item-assets/ |
| pystac-ext-label | 1.0.3 | Apache Software License | https://pypi.org/project/pystac-ext-label/ |
| pystac-ext-mgrs | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-mgrs/ |
| pystac-ext-mlm | 1.4.2 | Apache Software License | https://pypi.org/project/pystac-ext-mlm/ |
| pystac-ext-pointcloud | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-pointcloud/ |
| pystac-ext-projection | 2.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-projection/ |
| pystac-ext-raster | 1.1.2 | Apache Software License | https://pypi.org/project/pystac-ext-raster/ |
| pystac-ext-render | 2.0.1 | Apache Software License | https://pypi.org/project/pystac-ext-render/ |
| pystac-ext-sar | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-sar/ |
| pystac-ext-sat | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-sat/ |
| pystac-ext-scientific | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-scientific/ |
| pystac-ext-storage | 2.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-storage/ |
| pystac-ext-table | 1.2.2 | Apache Software License | https://pypi.org/project/pystac-ext-table/ |
| pystac-ext-timestamps | 1.1.2 | Apache Software License | https://pypi.org/project/pystac-ext-timestamps/ |
| pystac-ext-version | 1.2.2 | Apache Software License | https://pypi.org/project/pystac-ext-version/ |
| pystac-ext-view | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-view/ |
| pystac-ext-xarray-assets | 1.0.2 | Apache Software License | https://pypi.org/project/pystac-ext-xarray-assets/ |
| python-dateutil | 4.0.0 | BSD-3-Clause | https://pypi.org/project/python-dateutil/ |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://pypi.org/project/python-dotenv/ |
| PyYAML | 6.0.4 | MIT License | https://pypi.org/project/PyYAML/ |
| rasterio | 1.5.2 | BSD-3-Clause | https://pypi.org/project/rasterio/ |
| requests | 2.34.2 | Apache Software License | https://pypi.org/project/requests/ |
| shapely | 2.2.0 | BSD-3-Clause | https://pypi.org/project/shapely/ |
| starlette | 1.10.0 | BSD-3-Clause | https://pypi.org/project/starlette/ |
| tinycss2 | 1.5.1 | BSD License | https://pypi.org/project/tinycss2/ |
| tinyhtml5 | 2.1.0 | MIT License | https://pypi.org/project/tinyhtml5/ |
| typing_extensions | 4.16.0 | PSF-2.0 | https://pypi.org/project/typing_extensions/ |
| typing-inspection | 0.4.5 | MIT | https://pypi.org/project/typing-inspection/ |
| tzdata | 2026.6 | Apache-2.0 | https://pypi.org/project/tzdata/ |
| urllib3 | 2.8.0 | MIT | https://pypi.org/project/urllib3/ |
| uvicorn | 0.54.0 | BSD-3-Clause | https://pypi.org/project/uvicorn/ |
| uvloop | 0.23.0 | Apache Software License, MIT License | https://pypi.org/project/uvloop/ |
| watchfiles | 1.3.0 | MIT License | https://pypi.org/project/watchfiles/ |
| weasyprint | 70.0 | BSD License | https://pypi.org/project/weasyprint/ |
| webencodings | 0.6.1 | BSD License | https://pypi.org/project/webencodings/ |
| websockets | 17.4 | BSD-3-Clause | https://pypi.org/project/websockets/ |

## Backend (Python): tylko testy i jakość kodu

| Pakiet | Wersja | Licencja | Źródło |
|---|---|---|---|
| ast_serialize | 0.13.1 | MIT | https://pypi.org/project/ast_serialize/ |
| iniconfig | 2.3.1 | MIT | https://pypi.org/project/iniconfig/ |
| librt | 0.17.0 | MIT | https://pypi.org/project/librt/ |
| mypy | 2.4.1 | MIT | https://pypi.org/project/mypy/ |
| mypy_extensions | 1.2.0 | MIT | https://pypi.org/project/mypy_extensions/ |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | https://pypi.org/project/packaging/ |
| pathspec | 1.1.1 | Mozilla Public License 2.0 (MPL 2.0) | https://pypi.org/project/pathspec/ |
| pluggy | 1.7.0 | MIT License | https://pypi.org/project/pluggy/ |
| Pygments | 2.21.0 | BSD-2-Clause | https://pypi.org/project/Pygments/ |
| pytest | 9.2.0 | MIT | https://pypi.org/project/pytest/ |
| pytest-asyncio | 1.5.0 | Apache-2.0 | https://pypi.org/project/pytest-asyncio/ |
| respx | 0.23.1 | BSD License | https://pypi.org/project/respx/ |
| ruff | 0.17.6 | MIT | https://pypi.org/project/ruff/ |
| types-python-dateutil | 2.9.0.20261116 | Apache-2.0 | https://pypi.org/project/types-python-dateutil/ |
| types-PyYAML | 6.0.12.20261113 | Apache-2.0 | https://pypi.org/project/types-PyYAML/ |

## Frontend (npm): zależności produkcyjne

| Pakiet | Wersja | Licencja | Źródło |
|---|---|---|---|
| @emnapi/core | 1.11.3 | MIT | https://www.npmjs.com/package/@emnapi/core |
| @emnapi/core | 2.0.0-beta.2 | MIT | https://www.npmjs.com/package/@emnapi/core |
| @emnapi/runtime | 1.11.3 | MIT | https://www.npmjs.com/package/@emnapi/runtime |
| @emnapi/runtime | 2.0.0-beta.2 | MIT | https://www.npmjs.com/package/@emnapi/runtime |
| @emnapi/wasi-threads | 1.2.3 | MIT | https://www.npmjs.com/package/@emnapi/wasi-threads |
| @emnapi/wasi-threads | 2.2.0 | MIT | https://www.npmjs.com/package/@emnapi/wasi-threads |
| @floating-ui/core | 1.8.0 | MIT | https://www.npmjs.com/package/@floating-ui/core |
| @floating-ui/dom | 1.8.0 | MIT | https://www.npmjs.com/package/@floating-ui/dom |
| @floating-ui/react-dom | 2.1.9 | MIT | https://www.npmjs.com/package/@floating-ui/react-dom |
| @floating-ui/utils | 0.2.12 | MIT | https://www.npmjs.com/package/@floating-ui/utils |
| @jridgewell/gen-mapping | 0.3.13 | MIT | https://www.npmjs.com/package/@jridgewell/gen-mapping |
| @jridgewell/remapping | 2.3.5 | MIT | https://www.npmjs.com/package/@jridgewell/remapping |
| @jridgewell/resolve-uri | 3.1.3 | MIT | https://www.npmjs.com/package/@jridgewell/resolve-uri |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT | https://www.npmjs.com/package/@jridgewell/sourcemap-codec |
| @jridgewell/trace-mapping | 0.3.31 | MIT | https://www.npmjs.com/package/@jridgewell/trace-mapping |
| @mapbox/jsonlint-lines-primitives | 2.0.3 | MIT | https://www.npmjs.com/package/@mapbox/jsonlint-lines-primitives |
| @mapbox/point-geometry | 1.1.0 | ISC | https://www.npmjs.com/package/@mapbox/point-geometry |
| @mapbox/tiny-sdf | 2.3.0 | BSD-2-Clause | https://www.npmjs.com/package/@mapbox/tiny-sdf |
| @mapbox/unitbezier | 1.0.0 | BSD-2-Clause | https://www.npmjs.com/package/@mapbox/unitbezier |
| @mapbox/vector-tile | 3.0.0 | BSD-3-Clause | https://www.npmjs.com/package/@mapbox/vector-tile |
| @maplibre/geojson-vt | 6.3.3 | ISC | https://www.npmjs.com/package/@maplibre/geojson-vt |
| @maplibre/maplibre-gl-style-spec | 26.9.0 | ISC | https://www.npmjs.com/package/@maplibre/maplibre-gl-style-spec |
| @maplibre/mlt | 1.3.0 | (MIT OR Apache-2.0) | https://www.npmjs.com/package/@maplibre/mlt |
| @maplibre/vt-pbf | 4.3.3 | MIT | https://www.npmjs.com/package/@maplibre/vt-pbf |
| @napi-rs/wasm-runtime | 1.2.2 | MIT | https://www.npmjs.com/package/@napi-rs/wasm-runtime |
| @napi-rs/wasm-runtime | 1.2.6 | MIT | https://www.npmjs.com/package/@napi-rs/wasm-runtime |
| @oxc-project/types | 0.156.0 | MIT | https://www.npmjs.com/package/@oxc-project/types |
| @radix-ui/number | 1.1.3 | MIT | https://www.npmjs.com/package/@radix-ui/number |
| @radix-ui/primitive | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/primitive |
| @radix-ui/react-accessible-icon | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-accessible-icon |
| @radix-ui/react-accordion | 1.3.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-accordion |
| @radix-ui/react-alert-dialog | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-alert-dialog |
| @radix-ui/react-arrow | 1.1.17 | MIT | https://www.npmjs.com/package/@radix-ui/react-arrow |
| @radix-ui/react-aspect-ratio | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-aspect-ratio |
| @radix-ui/react-avatar | 1.3.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-avatar |
| @radix-ui/react-checkbox | 1.4.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-checkbox |
| @radix-ui/react-collapsible | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-collapsible |
| @radix-ui/react-collection | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-collection |
| @radix-ui/react-compose-refs | 1.1.5 | MIT | https://www.npmjs.com/package/@radix-ui/react-compose-refs |
| @radix-ui/react-context | 1.3.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-context |
| @radix-ui/react-context-menu | 2.4.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-context-menu |
| @radix-ui/react-dialog | 1.3.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-dialog |
| @radix-ui/react-direction | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-direction |
| @radix-ui/react-dismissable-layer | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-dismissable-layer |
| @radix-ui/react-dropdown-menu | 2.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-dropdown-menu |
| @radix-ui/react-focus-guards | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-focus-guards |
| @radix-ui/react-focus-scope | 1.3.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-focus-scope |
| @radix-ui/react-form | 0.3.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-form |
| @radix-ui/react-hover-card | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-hover-card |
| @radix-ui/react-id | 1.1.4 | MIT | https://www.npmjs.com/package/@radix-ui/react-id |
| @radix-ui/react-label | 2.1.17 | MIT | https://www.npmjs.com/package/@radix-ui/react-label |
| @radix-ui/react-menu | 2.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-menu |
| @radix-ui/react-menubar | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-menubar |
| @radix-ui/react-navigation-menu | 1.4.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-navigation-menu |
| @radix-ui/react-one-time-password-field | 0.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-one-time-password-field |
| @radix-ui/react-password-toggle-field | 0.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-password-toggle-field |
| @radix-ui/react-popover | 1.3.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-popover |
| @radix-ui/react-popper | 1.4.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-popper |
| @radix-ui/react-portal | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-portal |
| @radix-ui/react-presence | 1.1.11 | MIT | https://www.npmjs.com/package/@radix-ui/react-presence |
| @radix-ui/react-primitive | 2.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-primitive |
| @radix-ui/react-progress | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-progress |
| @radix-ui/react-radio-group | 1.5.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-radio-group |
| @radix-ui/react-roving-focus | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-roving-focus |
| @radix-ui/react-scroll-area | 1.4.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-scroll-area |
| @radix-ui/react-select | 2.4.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-select |
| @radix-ui/react-separator | 1.2.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-separator |
| @radix-ui/react-slider | 1.6.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-slider |
| @radix-ui/react-slot | 1.5.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-slot |
| @radix-ui/react-switch | 1.4.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-switch |
| @radix-ui/react-tabs | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-tabs |
| @radix-ui/react-toast | 1.3.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-toast |
| @radix-ui/react-toggle | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-toggle |
| @radix-ui/react-toggle-group | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-toggle-group |
| @radix-ui/react-toolbar | 1.2.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-toolbar |
| @radix-ui/react-tooltip | 1.4.1 | MIT | https://www.npmjs.com/package/@radix-ui/react-tooltip |
| @radix-ui/react-use-callback-ref | 1.1.5 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-callback-ref |
| @radix-ui/react-use-controllable-state | 1.3.0 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-controllable-state |
| @radix-ui/react-use-effect-event | 0.0.5 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-effect-event |
| @radix-ui/react-use-escape-keydown | 1.1.6 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-escape-keydown |
| @radix-ui/react-use-is-hydrated | 0.1.3 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-is-hydrated |
| @radix-ui/react-use-layout-effect | 1.1.4 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-layout-effect |
| @radix-ui/react-use-previous | 1.1.4 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-previous |
| @radix-ui/react-use-rect | 1.1.4 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-rect |
| @radix-ui/react-use-size | 1.1.5 | MIT | https://www.npmjs.com/package/@radix-ui/react-use-size |
| @radix-ui/react-visually-hidden | 1.2.13 | MIT | https://www.npmjs.com/package/@radix-ui/react-visually-hidden |
| @radix-ui/rect | 1.1.3 | MIT | https://www.npmjs.com/package/@radix-ui/rect |
| @rolldown/binding-android-arm-eabi | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-android-arm-eabi |
| @rolldown/binding-android-arm64 | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-android-arm64 |
| @rolldown/binding-darwin-arm64 | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-darwin-arm64 |
| @rolldown/binding-darwin-x64 | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-darwin-x64 |
| @rolldown/binding-freebsd-x64 | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-freebsd-x64 |
| @rolldown/binding-linux-arm-gnueabihf | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-linux-arm-gnueabihf |
| @rolldown/binding-linux-arm64-gnu | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-linux-arm64-gnu |
| @rolldown/binding-linux-arm64-musl | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-linux-arm64-musl |
| @rolldown/binding-linux-ppc64-gnu | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-linux-ppc64-gnu |
| @rolldown/binding-linux-s390x-gnu | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-linux-s390x-gnu |
| @rolldown/binding-linux-x64-gnu | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-linux-x64-gnu |
| @rolldown/binding-linux-x64-musl | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-linux-x64-musl |
| @rolldown/binding-openharmony-arm64 | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-openharmony-arm64 |
| @rolldown/binding-wasm32-wasi | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-wasm32-wasi |
| @rolldown/binding-win32-arm64-msvc | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-win32-arm64-msvc |
| @rolldown/binding-win32-x64-msvc | 1.2.19 | MIT | https://www.npmjs.com/package/@rolldown/binding-win32-x64-msvc |
| @rolldown/pluginutils | 1.1.1 | MIT | https://www.npmjs.com/package/@rolldown/pluginutils |
| @tailwindcss/node | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/node |
| @tailwindcss/oxide | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide |
| @tailwindcss/oxide-android-arm64 | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-android-arm64 |
| @tailwindcss/oxide-darwin-arm64 | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-darwin-arm64 |
| @tailwindcss/oxide-darwin-x64 | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-darwin-x64 |
| @tailwindcss/oxide-freebsd-x64 | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-freebsd-x64 |
| @tailwindcss/oxide-linux-arm-gnueabihf | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-linux-arm-gnueabihf |
| @tailwindcss/oxide-linux-arm64-gnu | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-linux-arm64-gnu |
| @tailwindcss/oxide-linux-arm64-musl | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-linux-arm64-musl |
| @tailwindcss/oxide-linux-x64-gnu | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-linux-x64-gnu |
| @tailwindcss/oxide-linux-x64-musl | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-linux-x64-musl |
| @tailwindcss/oxide-wasm32-wasi | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-wasm32-wasi |
| @tailwindcss/oxide-win32-arm64-msvc | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-win32-arm64-msvc |
| @tailwindcss/oxide-win32-x64-msvc | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/oxide-win32-x64-msvc |
| @tailwindcss/vite | 4.3.5 | MIT | https://www.npmjs.com/package/@tailwindcss/vite |
| @tybys/wasm-util | 0.10.3 | MIT | https://www.npmjs.com/package/@tybys/wasm-util |
| @tybys/wasm-util | 0.10.5 | MIT | https://www.npmjs.com/package/@tybys/wasm-util |
| @types/geojson | 7946.0.16 | MIT | https://www.npmjs.com/package/@types/geojson |
| @types/node | 24.19.2 | MIT | https://www.npmjs.com/package/@types/node |
| @types/react | 19.3.0 | MIT | https://www.npmjs.com/package/@types/react |
| @types/react-dom | 19.3.0 | MIT | https://www.npmjs.com/package/@types/react-dom |
| aria-hidden | 1.2.6 | MIT | https://www.npmjs.com/package/aria-hidden |
| bidi-js | 1.1.0 | MIT | https://www.npmjs.com/package/bidi-js |
| class-variance-authority | 0.7.1 | Apache-2.0 | https://www.npmjs.com/package/class-variance-authority |
| clsx | 2.1.1 | MIT | https://www.npmjs.com/package/clsx |
| cn | 0.5.2 | MIT | https://www.npmjs.com/package/cn |
| cookie | 1.1.1 | MIT | https://www.npmjs.com/package/cookie |
| csstype | 3.2.4 | MIT | https://www.npmjs.com/package/csstype |
| detect-libc | 2.1.2 | Apache-2.0 | https://www.npmjs.com/package/detect-libc |
| detect-node-es | 1.1.0 | MIT | https://www.npmjs.com/package/detect-node-es |
| earcut | 3.2.4 | ISC | https://www.npmjs.com/package/earcut |
| enhanced-resolve | 5.27.0 | MIT | https://www.npmjs.com/package/enhanced-resolve |
| fdir | 6.5.0 | MIT | https://www.npmjs.com/package/fdir |
| fsevents | 2.3.3 | MIT | https://www.npmjs.com/package/fsevents |
| get-nonce | 1.0.1 | MIT | https://www.npmjs.com/package/get-nonce |
| gl-matrix | 3.4.4 | MIT | https://www.npmjs.com/package/gl-matrix |
| graceful-fs | 4.2.12 | BlueOak-1.0.0 | https://www.npmjs.com/package/graceful-fs |
| jiti | 2.7.0 | MIT | https://www.npmjs.com/package/jiti |
| json-stringify-pretty-compact | 4.0.0 | MIT | https://www.npmjs.com/package/json-stringify-pretty-compact |
| kdbush | 4.1.0 | ISC | https://www.npmjs.com/package/kdbush |
| lightningcss | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss |
| lightningcss-android-arm64 | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-android-arm64 |
| lightningcss-darwin-arm64 | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-darwin-arm64 |
| lightningcss-darwin-x64 | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-darwin-x64 |
| lightningcss-freebsd-x64 | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-freebsd-x64 |
| lightningcss-linux-arm-gnueabihf | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-linux-arm-gnueabihf |
| lightningcss-linux-arm64-gnu | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-linux-arm64-gnu |
| lightningcss-linux-arm64-musl | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-linux-arm64-musl |
| lightningcss-linux-x64-gnu | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-linux-x64-gnu |
| lightningcss-linux-x64-musl | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-linux-x64-musl |
| lightningcss-win32-arm64-msvc | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-win32-arm64-msvc |
| lightningcss-win32-x64-msvc | 1.33.0 | MPL-2.0 | https://www.npmjs.com/package/lightningcss-win32-x64-msvc |
| lucide-react | 1.77.0 | ISC | https://www.npmjs.com/package/lucide-react |
| magic-string | 1.4.5 | MIT | https://www.npmjs.com/package/magic-string |
| maplibre-gl | 6.19.0 | BSD-3-Clause | https://www.npmjs.com/package/maplibre-gl |
| minimist | 1.2.8 | MIT | https://www.npmjs.com/package/minimist |
| murmurhash-js | 1.0.0 | MIT | https://www.npmjs.com/package/murmurhash-js |
| nanoid | 3.3.20 | MIT | https://www.npmjs.com/package/nanoid |
| pbf | 5.2.0 | BSD-3-Clause | https://www.npmjs.com/package/pbf |
| picocolors | 1.1.1 | ISC | https://www.npmjs.com/package/picocolors |
| picomatch | 4.0.7 | MIT | https://www.npmjs.com/package/picomatch |
| postcss | 8.5.33 | MIT | https://www.npmjs.com/package/postcss |
| potpack | 2.1.0 | ISC | https://www.npmjs.com/package/potpack |
| protocol-buffers-schema | 3.6.1 | MIT | https://www.npmjs.com/package/protocol-buffers-schema |
| quickselect | 3.0.0 | ISC | https://www.npmjs.com/package/quickselect |
| radix-ui | 1.8.1 | MIT | https://www.npmjs.com/package/radix-ui |
| react | 19.3.1 | MIT | https://www.npmjs.com/package/react |
| react-dom | 19.3.1 | MIT | https://www.npmjs.com/package/react-dom |
| react-remove-scroll | 2.7.2 | MIT | https://www.npmjs.com/package/react-remove-scroll |
| react-remove-scroll-bar | 2.3.8 | MIT | https://www.npmjs.com/package/react-remove-scroll-bar |
| react-router | 7.18.6 | MIT | https://www.npmjs.com/package/react-router |
| react-router-dom | 7.18.6 | MIT | https://www.npmjs.com/package/react-router-dom |
| react-style-singleton | 2.2.3 | MIT | https://www.npmjs.com/package/react-style-singleton |
| require-from-string | 2.0.2 | MIT | https://www.npmjs.com/package/require-from-string |
| rolldown | 1.2.19 | MIT | https://www.npmjs.com/package/rolldown |
| scheduler | 0.28.0 | MIT | https://www.npmjs.com/package/scheduler |
| set-cookie-parser | 2.7.3 | MIT | https://www.npmjs.com/package/set-cookie-parser |
| source-map-js | 1.2.4 | BSD-3-Clause | https://www.npmjs.com/package/source-map-js |
| tailwind-merge | 3.7.1 | MIT | https://www.npmjs.com/package/tailwind-merge |
| tailwindcss | 4.3.5 | MIT | https://www.npmjs.com/package/tailwindcss |
| tapable | 2.3.4 | MIT | https://www.npmjs.com/package/tapable |
| tinyglobby | 0.2.17 | MIT | https://www.npmjs.com/package/tinyglobby |
| tinyqueue | 3.0.0 | ISC | https://www.npmjs.com/package/tinyqueue |
| tslib | 2.8.1 | 0BSD | https://www.npmjs.com/package/tslib |
| tslib | 2.9.1 | 0BSD | https://www.npmjs.com/package/tslib |
| tw-animate-css | 1.4.0 | MIT | https://www.npmjs.com/package/tw-animate-css |
| undici-types | 7.24.6 | MIT | https://www.npmjs.com/package/undici-types |
| use-callback-ref | 1.3.3 | MIT | https://www.npmjs.com/package/use-callback-ref |
| use-sidecar | 1.1.3 | MIT | https://www.npmjs.com/package/use-sidecar |
| vite | 8.3.8 | MIT | https://www.npmjs.com/package/vite |
| zustand | 5.1.0 | MIT | https://www.npmjs.com/package/zustand |

## Frontend (npm): tylko budowanie i testy

| Pakiet | Wersja | Licencja | Źródło |
|---|---|---|---|
| @babel/code-frame | 7.29.7 | MIT | https://www.npmjs.com/package/@babel/code-frame |
| @babel/compat-data | 7.29.7 | MIT | https://www.npmjs.com/package/@babel/compat-data |
| @babel/core | 7.29.13 | MIT | https://www.npmjs.com/package/@babel/core |
| @babel/generator | 7.29.15 | MIT | https://www.npmjs.com/package/@babel/generator |
| @babel/helper-compilation-targets | 7.29.13 | MIT | https://www.npmjs.com/package/@babel/helper-compilation-targets |
| @babel/helper-globals | 7.29.7 | MIT | https://www.npmjs.com/package/@babel/helper-globals |
| @babel/helper-module-imports | 7.29.7 | MIT | https://www.npmjs.com/package/@babel/helper-module-imports |
| @babel/helper-module-transforms | 7.29.14 | MIT | https://www.npmjs.com/package/@babel/helper-module-transforms |
| @babel/helper-string-parser | 7.29.15 | MIT | https://www.npmjs.com/package/@babel/helper-string-parser |
| @babel/helper-validator-identifier | 7.29.7 | MIT | https://www.npmjs.com/package/@babel/helper-validator-identifier |
| @babel/helper-validator-option | 7.29.7 | MIT | https://www.npmjs.com/package/@babel/helper-validator-option |
| @babel/helpers | 7.29.15 | MIT | https://www.npmjs.com/package/@babel/helpers |
| @babel/parser | 7.29.15 | MIT | https://www.npmjs.com/package/@babel/parser |
| @babel/template | 7.29.7 | MIT | https://www.npmjs.com/package/@babel/template |
| @babel/traverse | 7.29.15 | MIT | https://www.npmjs.com/package/@babel/traverse |
| @babel/types | 7.29.15 | MIT | https://www.npmjs.com/package/@babel/types |
| @cacheable/memory | 2.2.0 | MIT | https://www.npmjs.com/package/@cacheable/memory |
| @cacheable/utils | 2.5.0 | MIT | https://www.npmjs.com/package/@cacheable/utils |
| @eslint-community/eslint-utils | 4.10.1 | MIT | https://www.npmjs.com/package/@eslint-community/eslint-utils |
| @eslint-community/regexpp | 4.12.3 | MIT | https://www.npmjs.com/package/@eslint-community/regexpp |
| @eslint/config-array | 0.23.6 | Apache-2.0 | https://www.npmjs.com/package/@eslint/config-array |
| @eslint/config-helpers | 0.7.0 | Apache-2.0 | https://www.npmjs.com/package/@eslint/config-helpers |
| @eslint/core | 1.2.1 | Apache-2.0 | https://www.npmjs.com/package/@eslint/core |
| @eslint/js | 10.0.1 | MIT | https://www.npmjs.com/package/@eslint/js |
| @eslint/object-schema | 3.0.5 | Apache-2.0 | https://www.npmjs.com/package/@eslint/object-schema |
| @eslint/plugin-kit | 0.7.3 | Apache-2.0 | https://www.npmjs.com/package/@eslint/plugin-kit |
| @humanfs/core | 0.19.2 | Apache-2.0 | https://www.npmjs.com/package/@humanfs/core |
| @humanfs/node | 0.16.8 | Apache-2.0 | https://www.npmjs.com/package/@humanfs/node |
| @humanfs/types | 0.15.0 | Apache-2.0 | https://www.npmjs.com/package/@humanfs/types |
| @humanwhocodes/module-importer | 1.0.1 | Apache-2.0 | https://www.npmjs.com/package/@humanwhocodes/module-importer |
| @humanwhocodes/retry | 0.4.3 | Apache-2.0 | https://www.npmjs.com/package/@humanwhocodes/retry |
| @isaacs/nonrecursive-glob-match | 1.1.0 | BlueOak-1.0.0 | https://www.npmjs.com/package/@isaacs/nonrecursive-glob-match |
| @keyv/bigmap | 1.3.1 | MIT | https://www.npmjs.com/package/@keyv/bigmap |
| @keyv/serialize | 1.1.1 | MIT | https://www.npmjs.com/package/@keyv/serialize |
| @types/chai | 5.2.3 | MIT | https://www.npmjs.com/package/@types/chai |
| @types/deep-eql | 4.0.2 | MIT | https://www.npmjs.com/package/@types/deep-eql |
| @types/esrecurse | 4.3.1 | MIT | https://www.npmjs.com/package/@types/esrecurse |
| @types/estree | 1.0.10 | MIT | https://www.npmjs.com/package/@types/estree |
| @types/json-schema | 7.0.15 | MIT | https://www.npmjs.com/package/@types/json-schema |
| @typescript-eslint/eslint-plugin | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/eslint-plugin |
| @typescript-eslint/parser | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/parser |
| @typescript-eslint/project-service | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/project-service |
| @typescript-eslint/scope-manager | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/scope-manager |
| @typescript-eslint/tsconfig-utils | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/tsconfig-utils |
| @typescript-eslint/type-utils | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/type-utils |
| @typescript-eslint/types | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/types |
| @typescript-eslint/typescript-estree | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/typescript-estree |
| @typescript-eslint/utils | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/utils |
| @typescript-eslint/visitor-keys | 8.73.0 | MIT | https://www.npmjs.com/package/@typescript-eslint/visitor-keys |
| @vitejs/plugin-react | 6.3.0 | MIT | https://www.npmjs.com/package/@vitejs/plugin-react |
| @vitest/mocker | 5.1.0 | MIT | https://www.npmjs.com/package/@vitest/mocker |
| @vitest/spy | 5.1.0 | MIT | https://www.npmjs.com/package/@vitest/spy |
| acorn | 8.19.0 | MIT | https://www.npmjs.com/package/acorn |
| acorn-jsx | 5.3.2 | MIT | https://www.npmjs.com/package/acorn-jsx |
| ajv | 6.15.0 | MIT | https://www.npmjs.com/package/ajv |
| assertion-error | 2.0.1 | MIT | https://www.npmjs.com/package/assertion-error |
| balanced-match | 4.0.4 | MIT | https://www.npmjs.com/package/balanced-match |
| baseline-browser-mapping | 2.11.39 | Apache-2.0 | https://www.npmjs.com/package/baseline-browser-mapping |
| brace-expansion | 5.0.13 | MIT | https://www.npmjs.com/package/brace-expansion |
| browserslist | 4.29.6 | MIT | https://www.npmjs.com/package/browserslist |
| cacheable | 2.5.0 | MIT | https://www.npmjs.com/package/cacheable |
| caniuse-lite | 1.0.30001826 | CC-BY-4.0 | https://www.npmjs.com/package/caniuse-lite |
| chai | 6.3.0 | MIT | https://www.npmjs.com/package/chai |
| convert-source-map | 2.0.0 | MIT | https://www.npmjs.com/package/convert-source-map |
| cross-spawn | 7.0.6 | MIT | https://www.npmjs.com/package/cross-spawn |
| debug | 4.4.3 | MIT | https://www.npmjs.com/package/debug |
| deep-is | 0.1.4 | MIT | https://www.npmjs.com/package/deep-is |
| electron-to-chromium | 1.5.492 | ISC | https://www.npmjs.com/package/electron-to-chromium |
| es-module-lexer | 2.3.2 | MIT | https://www.npmjs.com/package/es-module-lexer |
| escalade | 3.2.0 | MIT | https://www.npmjs.com/package/escalade |
| escape-string-regexp | 4.0.0 | MIT | https://www.npmjs.com/package/escape-string-regexp |
| eslint | 10.15.0 | MIT | https://www.npmjs.com/package/eslint |
| eslint-plugin-react-hooks | 7.1.1 | MIT | https://www.npmjs.com/package/eslint-plugin-react-hooks |
| eslint-plugin-react-refresh | 0.5.8 | MIT | https://www.npmjs.com/package/eslint-plugin-react-refresh |
| eslint-scope | 9.1.2 | BSD-2-Clause | https://www.npmjs.com/package/eslint-scope |
| eslint-visitor-keys | 3.4.3 | Apache-2.0 | https://www.npmjs.com/package/eslint-visitor-keys |
| eslint-visitor-keys | 5.0.1 | Apache-2.0 | https://www.npmjs.com/package/eslint-visitor-keys |
| espree | 11.2.0 | BSD-2-Clause | https://www.npmjs.com/package/espree |
| esquery | 1.7.0 | BSD-3-Clause | https://www.npmjs.com/package/esquery |
| esrecurse | 4.3.0 | BSD-2-Clause | https://www.npmjs.com/package/esrecurse |
| estraverse | 5.3.0 | BSD-2-Clause | https://www.npmjs.com/package/estraverse |
| estree-walker | 3.0.3 | MIT | https://www.npmjs.com/package/estree-walker |
| esutils | 2.0.3 | BSD-2-Clause | https://www.npmjs.com/package/esutils |
| expect-type | 1.4.0 | Apache-2.0 | https://www.npmjs.com/package/expect-type |
| fast-deep-equal | 3.1.3 | MIT | https://www.npmjs.com/package/fast-deep-equal |
| fast-json-stable-stringify | 2.1.0 | MIT | https://www.npmjs.com/package/fast-json-stable-stringify |
| fast-levenshtein | 2.0.6 | MIT | https://www.npmjs.com/package/fast-levenshtein |
| file-entry-cache | 11.1.5 | MIT | https://www.npmjs.com/package/file-entry-cache |
| find-up | 5.0.0 | MIT | https://www.npmjs.com/package/find-up |
| flat-cache | 6.1.23 | MIT | https://www.npmjs.com/package/flat-cache |
| flatted | 3.4.4 | ISC | https://www.npmjs.com/package/flatted |
| gensync | 1.0.0-beta.2 | MIT | https://www.npmjs.com/package/gensync |
| glob-parent | 6.0.2 | ISC | https://www.npmjs.com/package/glob-parent |
| globals | 17.14.0 | MIT | https://www.npmjs.com/package/globals |
| hashery | 1.5.1 | MIT | https://www.npmjs.com/package/hashery |
| hermes-estree | 0.25.1 | MIT | https://www.npmjs.com/package/hermes-estree |
| hermes-parser | 0.25.1 | MIT | https://www.npmjs.com/package/hermes-parser |
| hookified | 1.15.1 | MIT | https://www.npmjs.com/package/hookified |
| hookified | 2.2.0 | MIT | https://www.npmjs.com/package/hookified |
| ignore | 5.3.2 | MIT | https://www.npmjs.com/package/ignore |
| ignore | 7.0.16 | MIT | https://www.npmjs.com/package/ignore |
| imurmurhash | 0.1.4 | MIT | https://www.npmjs.com/package/imurmurhash |
| is-extglob | 2.1.1 | MIT | https://www.npmjs.com/package/is-extglob |
| is-glob | 4.0.3 | MIT | https://www.npmjs.com/package/is-glob |
| isexe | 2.0.0 | ISC | https://www.npmjs.com/package/isexe |
| js-tokens | 4.0.0 | MIT | https://www.npmjs.com/package/js-tokens |
| jsesc | 3.1.0 | MIT | https://www.npmjs.com/package/jsesc |
| json-schema-traverse | 0.4.1 | MIT | https://www.npmjs.com/package/json-schema-traverse |
| json-stable-stringify-without-jsonify | 1.0.1 | MIT | https://www.npmjs.com/package/json-stable-stringify-without-jsonify |
| json5 | 2.2.3 | MIT | https://www.npmjs.com/package/json5 |
| keyv | 5.6.0 | MIT | https://www.npmjs.com/package/keyv |
| levn | 0.4.1 | MIT | https://www.npmjs.com/package/levn |
| locate-path | 6.0.0 | MIT | https://www.npmjs.com/package/locate-path |
| lru-cache | 5.1.1 | ISC | https://www.npmjs.com/package/lru-cache |
| minimatch | 11.0.9 | BlueOak-1.0.0 | https://www.npmjs.com/package/minimatch |
| ms | 2.1.3 | MIT | https://www.npmjs.com/package/ms |
| natural-compare | 1.4.0 | MIT | https://www.npmjs.com/package/natural-compare |
| node-releases | 2.0.65 | MIT | https://www.npmjs.com/package/node-releases |
| obug | 3.0.0 | MIT | https://www.npmjs.com/package/obug |
| optionator | 0.9.4 | MIT | https://www.npmjs.com/package/optionator |
| p-limit | 3.1.0 | MIT | https://www.npmjs.com/package/p-limit |
| p-locate | 5.0.0 | MIT | https://www.npmjs.com/package/p-locate |
| path-exists | 4.0.0 | MIT | https://www.npmjs.com/package/path-exists |
| path-key | 3.1.1 | MIT | https://www.npmjs.com/package/path-key |
| prelude-ls | 1.2.1 | MIT | https://www.npmjs.com/package/prelude-ls |
| punycode | 2.3.1 | MIT | https://www.npmjs.com/package/punycode |
| qified | 0.10.1 | MIT | https://www.npmjs.com/package/qified |
| semver | 6.3.2 | ISC | https://www.npmjs.com/package/semver |
| semver | 7.8.6 | ISC | https://www.npmjs.com/package/semver |
| shebang-command | 2.0.0 | MIT | https://www.npmjs.com/package/shebang-command |
| shebang-regex | 3.0.0 | MIT | https://www.npmjs.com/package/shebang-regex |
| std-env | 4.3.0 | MIT | https://www.npmjs.com/package/std-env |
| tinybench | 6.2.4 | MIT | https://www.npmjs.com/package/tinybench |
| tinyexec | 1.3.1 | MIT | https://www.npmjs.com/package/tinyexec |
| ts-api-utils | 2.5.0 | MIT | https://www.npmjs.com/package/ts-api-utils |
| type-check | 0.4.0 | MIT | https://www.npmjs.com/package/type-check |
| typescript | 6.0.3 | Apache-2.0 | https://www.npmjs.com/package/typescript |
| typescript-eslint | 8.73.0 | MIT | https://www.npmjs.com/package/typescript-eslint |
| update-browserslist-db | 1.4.0 | MIT | https://www.npmjs.com/package/update-browserslist-db |
| uri-js | 4.4.1 | BSD-2-Clause | https://www.npmjs.com/package/uri-js |
| vitest | 5.1.0 | MIT | https://www.npmjs.com/package/vitest |
| which | 2.0.2 | ISC | https://www.npmjs.com/package/which |
| why-is-node-running | 3.2.1 | MIT | https://www.npmjs.com/package/why-is-node-running |
| word-wrap | 1.2.5 | MIT | https://www.npmjs.com/package/word-wrap |
| yallist | 3.1.1 | ISC | https://www.npmjs.com/package/yallist |
| yocto-queue | 0.1.0 | MIT | https://www.npmjs.com/package/yocto-queue |
| zod | 4.6.7 | MIT | https://www.npmjs.com/package/zod |
| zod-validation-error | 4.0.2 | MIT | https://www.npmjs.com/package/zod-validation-error |

## Obraz Docker i pakiety systemowe

| Komponent | Licencja | Źródło |
|---|---|---|
| node:22-slim (tylko etap budowania frontu) | MIT (Node.js) + pakiety Debian | https://hub.docker.com/_/node |
| python:3.12-slim-trixie | PSF-2.0 (Python) + pakiety Debian (licencje DFSG) | https://hub.docker.com/_/python |
| libpango-1.0-0, libpangoft2-1.0-0, libharfbuzz-subset0 | LGPL-2.1+ (Pango), MIT (HarfBuzz) | https://packages.debian.org/ |
| fonts-dejavu-core, fonts-liberation | Bitstream Vera / SIL OFL 1.1 | https://packages.debian.org/ |
| caddy:2.10-alpine | Apache-2.0 | https://hub.docker.com/_/caddy |
