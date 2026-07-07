# Homebrew formula for ClipFetch.
#
# This is a template for a future `brew install clipfetch`. It cannot be
# finalised until the package is published to PyPI (issue #8): fill in the
# real sdist `url` and `sha256` from https://pypi.org/project/clipfetch/#files,
# then run `brew audit --new clipfetch` and submit to a tap.
#
# Note: ClipFetch also needs a Chromium build at runtime — after install,
# users run `playwright install chromium` once. Document this in the caveats.
class Clipfetch < Formula
  include Language::Python::Virtualenv

  desc "Download short-form videos from your feed to watch offline"
  homepage "https://github.com/georgyia/ClipFetch"
  url "https://files.pythonhosted.org/packages/source/c/clipfetch/clipfetch-0.2.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"

  depends_on "python@3.12"

  # `brew update-python-resources clipfetch` regenerates these resource blocks
  # (playwright and its dependencies) once the package is on PyPI.

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      ClipFetch drives a Chromium browser. Install it once with:
        playwright install chromium
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/clipfetch --version")
  end
end
