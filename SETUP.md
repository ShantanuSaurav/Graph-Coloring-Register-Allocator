# Pushing this to GitHub

Do this once, from whoever's account will host the repo.

## 1. Create the empty repo

Go to github.com, click **New repository**. Name it `regalloc-a5`. **Do not** tick
"Add a README" — this folder already has one, and initialising it there causes a
merge conflict on your first push.

## 2. Push this folder

```bash
cd regalloc-a5
git init
git add .
git commit -m "Initial commit: project structure, IR parser, test suite"
git branch -M main
git remote add origin https://github.com/<your-username>/regalloc-a5.git
git push -u origin main
```

## 3. Add the other three members

Repo **Settings** → **Collaborators** → **Add people**. They need write access to push
branches.

## 4. Each member creates their branch

```bash
git checkout -b m1-frontend      # M1
git checkout -b m2-analysis      # M2
git checkout -b m3-colouring     # M3
git checkout -b m4-spilling      # M4
git push -u origin <branch-name>
```

## 5. Protect main (optional, looks good at review)

**Settings** → **Branches** → **Add rule** for `main`:
- Require a pull request before merging
- Require status checks to pass (select the `pytest` check once CI has run once)

This is what backs up the claim in your deck that every merge is reviewed.

---

## Making sure commits are attributable

The Review 1 checklist asks for "identifiable member commits". Each member should set
their identity **before** their first commit:

```bash
git config user.name "Your Name"
git config user.email "your-github-email@example.com"
```

Use the same email as your GitHub account, or commits won't link to your profile and
won't count as evidence of your contribution.

Check who has committed what:

```bash
git shortlog -sn
```

## First thing to do after pushing

Fill in the blanks in `README.md`: team number, member names and register numbers,
and the repo URL. Then update `docs/contribution_log.md` after every meeting.
