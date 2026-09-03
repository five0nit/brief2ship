# Talking avatar repo-first case study

This captures a workflow correction from a talking-avatar session.

## What went wrong

The initial attempt built a custom mouth-overlay/2D cutout script before comparing existing repositories. The user correctly pointed to `met4citizen/talkinghead`, which was a better base for the **3D rigged avatar** version of the task.

## Durable lesson

For new build/prototype tasks, especially media/AI/avatar workflows:

1. Search available repos/tools first.
2. Score candidates visibly.
3. Choose the best base before writing custom code.
4. Only build cleanly from scratch if no candidate fits.

## Candidate distinction from this case

- `met4citizen/TalkingHead`: strong base for 3D rigged avatars with GLB morph targets / visemes.
- 2D puppet / South Park-style talking image: different class; requires flat layered puppet rig or image-animation tool.
- Arbitrary uploaded screenshot: not directly usable by TalkingHead unless rebuilt/converted into a rigged avatar.

## Example scoring outcome

For query: `talking avatar lip sync javascript`

| Score | Candidate | Why |
|---:|---|---|
| 88 | `met4citizen/TalkingHead` | MIT, active enough, direct 3D talking-avatar/lip-sync fit |
| 75 | `lexziconAI/TalkingHead` | Fork/copy with lower confidence |

## Recommended next step after choosing TalkingHead

Do not immediately customize the user asset. First run a deterministic proof with a bundled local GLB and explicit viseme timings. Then adapt to the desired branded avatar.
