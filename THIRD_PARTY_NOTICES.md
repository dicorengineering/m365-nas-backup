# Third-party notices and source availability

The project-owned application code is MIT licensed; see LICENSE.
That license does not replace any dependency, Python interpreter, Linux component,
bundled native library, service or trademark license.

## Python runtime packages

[third_party/python-packages.json](third_party/python-packages.json) records the
pinned runtime versions, upstream licensing metadata and source URLs.
[third_party/licenses](third_party/licenses) retains the full license/notice files
shipped with those installed distributions, including Requests' NOTICE and the
dual Apache/BSD cryptography texts. These files are copied without modification.

Certifi is MPL-2.0, not MIT. The full [MPL-2.0 text](third_party/licenses/MPL-2.0.txt)
is included alongside its upstream notice. Its unmodified source distribution and certificate data
are available from [PyPI](https://pypi.org/project/certifi/) and the source bundle
distributed with the matching public image release. Its license applies to its
covered files; it does not relicense the separate application.

Some packages contain compiled code or bundled components. Their upstream notices
and source distributions remain applicable. The release's image inventory includes
the actual Linux-installed distributions, which can differ from a development host.

## Container components

The container additionally distributes CPython, pip and Debian GNU/Linux packages.
Their licenses are separate, including PSF, BSD, MIT, Apache, GPL and LGPL licenses.
The image keeps the installed Python distribution notices and Debian's
/usr/share/doc/<package>/copyright and /usr/share/common-licenses files.

Starting with alpha 8, /usr/share/m365-nas-backup/licenses contains the application
license/disclaimer, collected Python license files and an exact installed package
inventory. The matching release supplies a notices archive and a dependency-source
archive alongside the image. It includes exact Debian source packages, source
archives for installed Python distributions, and the CPython source used by the base
image, plus checksums and retrieval metadata. Build recipes are this repository's
Dockerfile and the upstream Python image recipe recorded with its revision and version.
The recipe record identifies whether its Python version matches the image. Source files are
redistributed under their respective licenses, not under the application's MIT license.

To redistribute an image, keep these notices and make the matching sources available
alongside your binaries where the relevant license requires it. Do not remove
upstream copyright or attribution files. Review changes to base images, native
libraries and dependencies before shipping a derivative.

## Development tools and services

GitHub Actions, Docker, test/browser tools and optional development dependencies
retain their own licenses. They are not relicensed by this repository.
Using Microsoft APIs or Outlook still requires the appropriate Microsoft account,
permissions and service/product licenses.

This inventory is a record of upstream notices and distribution inputs, not a legal
opinion or a guarantee that every downstream use satisfies every obligation.
