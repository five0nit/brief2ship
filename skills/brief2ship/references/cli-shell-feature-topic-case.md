# CLI shell feature topic case: repo-first fallback pattern

Session context: user asked to use the repo-first starter for topic `CLI Tools Korn shell and C shell features`.

## What happened

The exact starter queries returned an empty table:

```bash
repo-first "CLI Tools Korn shell and C shell features" --limit 8
repo-first "KornShell ksh csh tcsh shell features CLI tools" --limit 8 --deep-github
```

Direct GitHub search on the broad phrase also returned little/no useful material, but authoritative source repos were discoverable by naming the canonical implementations directly:

```bash
gh repo view ksh93/ksh --json nameWithOwner,description,stargazerCount,forkCount,licenseInfo,issues,updatedAt,url,defaultBranchRef,homepageUrl
gh repo view tcsh-org/tcsh --json nameWithOwner,description,stargazerCount,forkCount,licenseInfo,issues,updatedAt,url,defaultBranchRef,homepageUrl
gh repo view mirabilos/mksh-cvs2git --json nameWithOwner,description,stargazerCount,forkCount,licenseInfo,issues,updatedAt,url,defaultBranchRef,homepageUrl
```

Then clone/inspect the authoritative candidates, rather than relying on README summaries:

```bash
mkdir -p /tmp/repo-first-shell-features
cd /tmp/repo-first-shell-features
git clone --depth 1 https://github.com/ksh93/ksh.git ksh
git clone --depth 1 https://github.com/tcsh-org/tcsh.git tcsh
```

Useful inspected files:

- `ksh/README.md` around its KSH-93 feature list.
- `tcsh/README.md` for the concise project description.
- `tcsh/tcsh.man.in` for command-line editing, completion, spelling correction, history, bindkey, and related interactive features.

## Durable lesson

For broad knowledge/comparison topics, `repo-first` may miss authoritative bases because the best matches are canonical implementation repos rather than repos whose descriptions contain the whole topic phrase. If the starter returns empty:

1. Broaden the terms.
2. Search direct implementation names and common aliases.
3. Query `gh repo view` for known canonical repos even if search did not find them.
4. Prefer a paired/multi-source reference base when the topic is comparative, e.g. `ksh93/ksh` + `tcsh-org/tcsh`, instead of forcing one repo to cover both sides.
5. Clone and inspect source/manpage files for receipts before producing a feature comparison.

## Candidate decision from this case

- Best Korn shell reference: `ksh93/ksh` — active KSH-93u+m source, EPL-2.0.
- Best C shell/tcsh reference: `tcsh-org/tcsh` — official/read-only tcsh mirror, homepage `https://www.tcsh.org/`.
- Secondary Korn-family comparison: `mirabilos/mksh-cvs2git` — MirBSD Korn shell mirror, useful but publish-only and license metadata not exposed by GitHub API.
