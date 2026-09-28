#!/usr/bin/env perl
# secrecy_scan.pl - check [6/8] of check_tex.sh: internal material left in the public build.
#
# Usage: perl secrecy_scan.pl <outdir> [public_labels.txt]
#
# Scans <outdir>/main.tex and <outdir>/main.txt (pdftotext -layout of the PDF).
#   FAIL  fixed strings (repository paths, markers), ledger ids (XXX-NN), placeholder text,
#         campaign names (j8_frontier), registration labels (hj12), and, in main.tex, stray
#         emphasis formed by a bare '*' in the markdown ("h*" twice in one paragraph gives
#         h\emph{), read ... h}). The preamble of main.tex is scanned for fixed strings only.
#   WARN  (PDF text only, one warning per category) short internal-looking labels (J10, LP-2)
#         not declared in public_labels.txt, hex commit SHAs, "lines N-M" references and
#         repository-style file names. These need a human decision, not a blanket ban.
# PDF text lines ending in '-' are joined with the next line and re-scanned; only a match
# that spans the join is counted, so no hit is counted twice.
# main.tex hits are mapped back to markdown line numbers (<outdir>/source_paper.txt, written
# by build.sh) and summarised per markdown line: that list is the content-side edit list.
# Last lines: TOTAL_SECRECY_FAILS <n> and TOTAL_SECRECY_WARNS <n>.
use strict;
use warnings;

binmode(STDOUT, ":encoding(UTF-8)");
binmode(STDERR, ":encoding(UTF-8)");

my ($outdir, $labels_file) = @ARGV;
die "usage: $0 <outdir> [public_labels.txt]\n" unless defined $outdir;

sub read_lines {
  my ($file) = @_;
  return () unless -f $file;
  my $fh;
  if (!open($fh, "<:encoding(UTF-8)", $file)) {
    open($fh, "<:raw", $file) or return ();
  }
  my @l = <$fh>;
  close $fh;
  chomp @l;
  return @l;
}

# ---------------------------------------------------------------- patterns
my @fixed_strings = (
  "docs/", "campaign/", "scripts/", "configs/", "src/", "tests/",
  "/scratch", "/home", "/mnt", "n12194778", ".claude", "iaes",
  "TODO", "NEEDS LEDGER", "NEEDS-LEDGER", "??"
);

# Ledger id: PREFIX(-PART)*-NN[a-z] with an optional ..NN range
my $ledger_re = qr/(?:^|[^A-Za-z0-9_-])([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-[0-9]{2}[a-z]?(?:\.\.[0-9]{2})?)(?=[^A-Za-z0-9_]|$)/;

# FAIL regexes: [summary key, description, regex capturing the offending text in $1]
my @fail_res = (
  ["LEDGER_ID",     "ledger ID pattern",   $ledger_re],
  ["PLACEHOLDER",   "placeholder text",    qr/(?<![A-Za-z])([Pp]laceholder|PLACEHOLDER|[Tt]o be filled|TBD|FIXME|XXX)(?![A-Za-z])/],
  ["CAMPAIGN_NAME", "internal campaign name", qr/(?<![A-Za-z0-9])(j[0-9]+_[a-z][a-z0-9_]*)/],
  ["REG_LABEL",     "internal registration label", qr/(?<![A-Za-z0-9])(hj[0-9]{2})(?![0-9])/],
);
# main.tex body only: an emphasis group that opens on punctuation or a space
my $stray_emph_re = qr/(\\(?:emph|textbf)\{[\s,;:.)][^}]{0,30})/;

# WARN regexes, PDF text only: [category, regex capturing the token in $1]
my @warn_res = (
  ["SHORT_LABEL", qr/(?<![A-Za-z0-9_.\/\-])([A-Z]{1,3}[0-9]{1,2}[a-z]?|[A-Z]{1,3}-[0-9])(?![A-Za-z0-9_])/],
  ["HEX_SHA",     qr/(?<![A-Za-z0-9])((?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40})(?![A-Za-z0-9])/],
  ["LINE_REF",    qr/(?<![A-Za-z])((?:lines?|l\.) ?[0-9]+ ?[-\x{2013}] ?[0-9]+)/],
  ["FILE_NAME",   qr/(?<![A-Za-z0-9_.\/-])([A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:jsonl?|py|md|ya?ml|csv|ipynb|sh|lua|pt|safetensors))(?![A-Za-z0-9])/],
);

my %public_label;
if (defined $labels_file && -f $labels_file) {
  for my $l (read_lines($labels_file)) {
    $l =~ s/#.*//;
    $l =~ s/^\s+|\s+$//g;
    $public_label{$_} = 1 for split /[\s,]+/, $l;
  }
  delete $public_label{""};
}

# ---------------------------------------------------------------- md line mapping
my @md;
my (%md_shingle, %md_short);
if (-f "$outdir/source_paper.txt") {
  my ($src) = read_lines("$outdir/source_paper.txt");
  @md = read_lines($src) if defined $src && -f $src;
}
sub words_of {
  my ($s, $is_tex) = @_;
  $s =~ s/\\[A-Za-z]+\*?//g if $is_tex;
  $s = lc $s;
  return ($s =~ /[a-z0-9]{3,}/g);
}
for my $i (0 .. $#md) {
  my @w = words_of($md[$i], 0);
  next unless @w;
  if (@w < 3) {
    $md_short{ join(" ", @w) } //= $i + 1;
    next;
  }
  for my $j (0 .. $#w - 2) {
    push @{ $md_shingle{"$w[$j] $w[$j+1] $w[$j+2]"} }, $i + 1;
  }
}
my %md_cache;
sub md_line_for {
  my ($tex_line) = @_;
  return "" unless @md;
  return $md_cache{$tex_line} if exists $md_cache{$tex_line};
  my @w = words_of($tex_line, 1);
  my $best = "";
  if (@w >= 3) {
    my %vote;
    for my $j (0 .. $#w - 2) {
      my $k = "$w[$j] $w[$j+1] $w[$j+2]";
      next unless $md_shingle{$k};
      my %once = map { $_ => 1 } @{ $md_shingle{$k} };
      $vote{$_}++ for keys %once;
    }
    my @c = sort { $vote{$b} <=> $vote{$a} || $a <=> $b } keys %vote;
    $best = $c[0] if @c && $vote{ $c[0] } >= 2;
  } elsif (@w) {
    $best = $md_short{ join(" ", @w) } // "";
  }
  $md_cache{$tex_line} = $best;
  return $best;
}

# ---------------------------------------------------------------- scanning
my (%pattern_counts, %by_md, %warn_tokens);
my ($main_tex_fails, $pdf_fails) = (0, 0);

sub snippet {
  my ($line, $pos) = @_;
  my $start = $pos > 25 ? $pos - 25 : 0;
  return substr($line, $start, 80);
}

# All FAIL hits on one line: [key, description, text, start, end]
sub fail_hits {
  my ($line, $is_tex_body) = @_;
  my @h;
  for my $pat (@fixed_strings) {
    my $pos = index($line, $pat);
    push @h, [$pat, "fixed pattern", $pat, $pos, $pos + length($pat)] if $pos >= 0;
  }
  for my $fr (@fail_res) {
    my ($key, $desc, $re) = @$fr;
    while ($line =~ /$re/g) {
      my $m = $1;
      my $end = $-[1] + length($m);
      push @h, [$key, $desc, $m, $-[1], $end];
    }
  }
  if ($is_tex_body) {
    while ($line =~ /$stray_emph_re/g) {
      push @h, ["STRAY_EMPHASIS", "stray emphasis from a bare * in the markdown (write \\*)", $1, $-[1], $-[1] + length($1)];
    }
  }
  return @h;
}

sub warn_hits {
  my ($line) = @_;
  my @h;
  for my $wr (@warn_res) {
    my ($cat, $re) = @$wr;
    while ($line =~ /$re/g) {
      my ($m, $st) = ($1, $-[1]);
      my $end = $st + length($m);
      if ($cat eq "SHORT_LABEL") {
        next if $public_label{$m};
        my $pre = substr($line, 0, $st);
        next if $pre =~ /(?:Tables?|Figures?|Appendix|Appendices)\s+$/;
        my ($wl) = $pre =~ /(\S*)$/;
        my ($wr2) = substr($line, $end) =~ /^(\S*)/;
        my $word = ($wl // "") . $m . ($wr2 // "");
        next if $word =~ m{/|://|www\.|doi\.org}i;
      }
      push @h, [$cat, $m];
    }
  }
  return @h;
}

sub report_fail {
  my ($where, $h, $line, $is_tex, $md_line) = @_;
  my ($key, $desc, $text, $st) = @$h;
  $pattern_counts{$key}++;
  if ($is_tex) { $main_tex_fails++ } else { $pdf_fails++ }
  my $md_tag = ($is_tex && $md_line ne "") ? " [md:$md_line]" : "";
  printf "FAIL: %s%s: %s \"%s\": ...%s...\n", $where, $md_tag, $desc, $text, snippet($line, $st);
}

# --- main.tex
my @tex = read_lines("$outdir/main.tex");
my $in_body = 0;
for my $i (0 .. $#tex) {
  my $raw = $tex[$i];
  $in_body = 1 if $raw =~ /\\begin\{document\}/;
  my $line = $raw;
  $line =~ s/\\allowbreak\{\}//g;
  $line =~ s/\\_/_/g;
  $line =~ s/\\-//g;
  my @hits = fail_hits($line, $in_body);
  @hits = grep { $_->[1] eq "fixed pattern" } @hits unless $in_body;
  next unless @hits;
  my $md_line = $in_body ? md_line_for($raw) : "";
  for my $h (@hits) {
    report_fail("main.tex:" . ($i + 1), $h, $line, 1, $md_line);
    my $k = $md_line ne "" ? $md_line : "?";
    $by_md{$k}{ $h->[0] eq "STRAY_EMPHASIS" ? "stray *-emphasis (write \\*)" : $h->[2] }++;
  }
}

# --- PDF text
my @txt = read_lines("$outdir/main.txt");
my $page = 1;
my @page_of;
for my $i (0 .. $#txt) {
  my $ff = () = $txt[$i] =~ /\f/g;
  $page += $ff;
  $page_of[$i] = $page;
  my $line = $txt[$i];
  $line =~ s/\f//g;
  $txt[$i] = $line;
  report_fail("main.txt:" . ($i + 1) . " p$page", $_, $line, 0, "") for fail_hits($line, 0);
  for my $h (warn_hits($line)) {
    my ($cat, $tok) = @$h;
    $warn_tokens{$cat}{$tok}{n}++;
    $warn_tokens{$cat}{$tok}{pages}{$page} = 1;
  }
}
# hyphen-split lines: count only matches that span the join
for my $i (0 .. $#txt - 1) {
  next unless $txt[$i] =~ /-\s*$/;
  (my $a = $txt[$i]) =~ s/\s+$//;
  (my $b = $txt[$i + 1]) =~ s/^\s+//;
  my $join = length($a);
  my $joined = $a . $b;
  for my $h (fail_hits($joined, 0)) {
    my ($st, $en) = @$h[3, 4];
    next unless $st < $join && $en > $join;
    report_fail("main.txt:" . ($i + 1) . "-" . ($i + 2) . " p$page_of[$i] (hyphen-joined)", $h, $joined, 0, "");
  }
}

my $total_fails = $main_tex_fails + $pdf_fails;

print "\nPer-file counts:\n";
print "  main.tex: $main_tex_fails\n";
print "  PDF text: $pdf_fails\n";

print "\nPattern match summary:\n";
print "  none\n" unless %pattern_counts;
for my $k (sort keys %pattern_counts) {
  print "  $k: $pattern_counts{$k} hit(s)\n";
}

my $warns = 0;
my %explain = (
  SHORT_LABEL => "short internal-looking labels: declare the ones the paper defines for readers in public_labels.txt, rephrase the rest",
  HEX_SHA     => "hex strings that look like commit SHAs",
  LINE_REF    => "line-number references (into files a reader cannot see?)",
  FILE_NAME   => "repository-style file names",
);
print "\nHeuristic checks (PDF text; each hit needs a human decision):\n";
print "  none\n" unless %warn_tokens;
for my $cat (qw(SHORT_LABEL HEX_SHA LINE_REF FILE_NAME)) {
  next unless $warn_tokens{$cat};
  $warns++;
  my $t = $warn_tokens{$cat};
  my @toks = sort { $t->{$b}{n} <=> $t->{$a}{n} || $a cmp $b } keys %$t;
  printf "WARN: %s: %d distinct (%s)\n", $cat, scalar(@toks), $explain{$cat};
  for my $tok (@toks) {
    my @p = sort { $a <=> $b } keys %{ $t->{$tok}{pages} };
    my $plist = join(",", @p > 12 ? (@p[0 .. 11], "...") : @p);
    printf "    %-36s x%-3d p%s\n", $tok, $t->{$tok}{n}, $plist;
  }
}
if (%public_label) {
  print "  public_labels.txt declares: " . join(" ", sort keys %public_label) . "\n";
}

if (%by_md) {
  print "\nContent-side edit list (main.tex FAIL hits by markdown line):\n";
  for my $k (sort { ($a eq "?" ? 1e9 : $a) <=> ($b eq "?" ? 1e9 : $b) } keys %by_md) {
    my $h = $by_md{$k};
    print "  md:$k: " . join(", ", map { $h->{$_} > 1 ? "$_ x$h->{$_}" : $_ } sort keys %$h) . "\n";
  }
}

print "TOTAL_SECRECY_FAILS $total_fails\n";
print "TOTAL_SECRECY_WARNS $warns\n";
