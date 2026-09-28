#!/usr/bin/env perl
# meta_ascii.pl - fold a pandoc plain-text rendering (abstract, title, authors) into the
# ASCII that arXiv's metadata form accepts.
#
# Usage: perl meta_ascii.pl <in.txt> <out.txt> <label>
#
# arXiv help/prep.html (fetched 2026-09-28): "Our metadata fields only accept ASCII input.
# Unicode characters should be converted to its TeX equivalent"; for the abstract,
# "Carriage returns will be stripped unless they are followed by leading white spaces"
# and "Avoid unnecessary blank lines"; TeX-isms such as "~" should be omitted.
#
# Known characters are mapped below. Anything left over is reported with its code point
# and context, and the script exits 3, so build.sh and check_tex.sh can FAIL on it.
use strict;
use warnings;

my ($in, $out, $label) = @ARGV;
die "usage: $0 <in> <out> <label>\n" unless defined $label;

open my $fh, '<:encoding(UTF-8)', $in or die "cannot read $in: $!\n";
local $/;
my $t = <$fh>;
close $fh;
$t = '' unless defined $t;

my %map = (
  "\x{2018}" => "'",  "\x{2019}" => "'",  "\x{201A}" => "'",  "\x{2032}" => "'",
  "\x{201C}" => '"',  "\x{201D}" => '"',  "\x{201E}" => '"',  "\x{2033}" => "''",
  "\x{2013}" => '-',  "\x{2014}" => '--', "\x{2212}" => '-',  "\x{2010}" => '-',
  "\x{2011}" => '-',  "\x{00AD}" => '',
  "\x{00A0}" => ' ',  "\x{2009}" => ' ',  "\x{202F}" => ' ',  "\x{2007}" => ' ',
  "\x{200A}" => ' ',  "\x{2002}" => ' ',  "\x{2003}" => ' ',  "\x{200B}" => '',
  "\x{2026}" => '...',
  "\x{00D7}" => 'x',  "\x{00B7}" => '*',
  "\x{2265}" => '>=', "\x{2264}" => '<=', "\x{2260}" => '!=', "\x{2248}" => '~',
  "\x{223C}" => '~',  "\x{00B1}" => '+/-',
  "\x{2192}" => '->', "\x{2190}" => '<-', "\x{2194}" => '<->', "\x{21D2}" => '=>',
  "\x{00B0}" => ' deg',
  "\x{03B1}" => '$\alpha$',   "\x{03B2}" => '$\beta$',   "\x{03B3}" => '$\gamma$',
  "\x{03B4}" => '$\delta$',   "\x{03B5}" => '$\epsilon$', "\x{03B8}" => '$\theta$',
  "\x{03BB}" => '$\lambda$',  "\x{03BC}" => '$\mu$',     "\x{03C0}" => '$\pi$',
  "\x{03C3}" => '$\sigma$',   "\x{03C4}" => '$\tau$',    "\x{0394}" => '$\Delta$',
  "\x{03A3}" => '$\Sigma$',   "\x{2208}" => '$\in$',
);

my $mapped = 0;
$t =~ s/([^\x00-\x7f])/exists $map{$1} ? do { $mapped++; $map{$1} } : $1/ge;

# Paragraph handling: pandoc plain separates paragraphs with a blank line. arXiv keeps a
# line break only when the next line starts with whitespace, and asks for no blank lines.
$t =~ s/\r//g;
$t =~ s/\t/ /g;
$t =~ s/ {2,}/ /g;
$t =~ s/ +\n/\n/g;
$t =~ s/\n +/\n/g;
$t =~ s/^\s+//;
$t =~ s/\s+$//;
my @paras = split /\n{2,}/, $t;
s/\n/ /g for @paras;       # a lone line break inside a paragraph becomes a space
$t = join("\n  ", @paras); # paragraph break -> newline + indent
$t .= "\n";

open my $oh, '>:encoding(UTF-8)', $out or die "cannot write $out: $!\n";
print $oh $t;
close $oh;

my @left;
while ($t =~ /(.{0,25})([^\x00-\x7f])(.{0,25})/g) {
  push @left, sprintf("U+%04X '%s' in: ...%s[%s]%s...", ord($2), $2, $1, $2, $3);
}
binmode STDOUT, ':encoding(UTF-8)';
my $chars = length($t);
printf "%s: %d chars after ASCII folding (%d characters mapped)\n", $label, $chars, $mapped;
if (@left) {
  print "$label: NON-ASCII left (arXiv metadata is ASCII-only):\n";
  print "  $_\n" for @left;
  exit 3;
}
exit 0;
