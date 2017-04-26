class Watchteleboy < Formula
  desc "Script to watch streams from teleboy.ch without browser/flash"
  homepage "https://github.com/reduzent/watchteleboy"
  url "https://github.com/reduzent/watchteleboy/archive/v1.28.zip"
  sha256 "1e4708aae07faf6e668d1d63a3c3fe806ab8d88f3aaff5a73665eb2dc7b52fcb"

  depends_on "coreutils"
  depends_on "gnu-sed"
  depends_on "jq"
  depends_on "mpv" => :recommended

  def install
    bin.install "watchteleboy"
    man1.install "DOCS/man/watchteleboy.1"
  end

  test do
    system "#{prefix}/bin/watchteleboy", "--help"
  end
end
