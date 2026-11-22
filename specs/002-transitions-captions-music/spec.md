# Feature Specification: Scene Transitions, Photo Captions, Subtitles, and Background Music

**Feature Branch**: `002-transitions-captions-music`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "@D:/CublickDigital-Codes/Movie_Agent/specify.txt" (Movie Maker integrated specification v0.3). This feature covers Release 2 of that document (section 7.2, requirements FR-041 to FR-051, and roadmap steps 2-1 to 2-6). Release 3 items (narration voice, storyboard editing, presets) are out of scope.

**Numbering**: Requirement and success-criteria numbers continue from feature 001 (FR-001 to FR-040, SC-001 to SC-008) so that both features can be traced in one product specification. All requirements of feature 001 still apply unless this document changes them.

## Clarifications

### Session 2026-11-21

- Q: Should users be able to review and correct the captions written from their photo notes before the video is made? → A: Yes. Before any scene is generated, the system shows the caption drafts; the user reviews or edits them and then confirms to start generation (FR-064). Editing after completion is not offered in this release.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Smooth Transitions Between Scenes (Priority: P1)

A user creating a video chooses a transition style, such as a fade or a slide, and receives a video in which each scene flows into the next instead of cutting abruptly. Scenes made by different engines or at slightly different sizes still join cleanly.

**Why this priority**: Every video has more than one scene, so the join between scenes affects every result. Placing scenes on one shared timeline is also the foundation that captions and music depend on.

**Independent Test**: Submit a photos-only job with four photos and the transition set to "fade". Download the video. Confirm that each scene change shows a visible fade, that all scenes have the same frame size, and that the video is shorter than the sum of the scene lengths by the overlap of the three transitions.

**Acceptance Scenarios**:

1. **Given** a job with three or more scenes and the transition set to "fade", **When** the job completes, **Then** every scene change in the video is a fade of the chosen length, and the first scene starts without a transition.
2. **Given** a job with the transition set to "none", **When** the job completes, **Then** the scenes are joined with straight cuts, and the result has the same scenes, order, and length as the same job produced by feature 001.
3. **Given** a job whose scenes were produced at different frame sizes or frame rates, **When** the scenes are joined, **Then** the final video has one frame size and one frame rate, matching the job's output options.
4. **Given** a job with the transition set to "auto", **When** the job completes, **Then** consecutive scene changes use different transition styles from the supported list.
5. **Given** a user who uses only a keyboard, **When** the user chooses a transition style and length, **Then** both choices can be made and confirmed without a mouse.

---

### User Story 2 - Captions Written from Notes on Each Photo (Priority: P1)

A user uploads several photos and types a short note for each one, such as "Grandma's 80th birthday, the whole family together". The finished video shows a short, readable caption on each photo's scene, written from that note.

**Why this priority**: This is the main reason users asked for the feature. A photo video without words does not tell the story the user has in mind.

**Independent Test**: Submit a photos-only job with three photos, each with a note, and agree to the text assistance disclosure. When the job is awaiting review, edit one caption and confirm. Download the video and its subtitle file. Confirm that each scene shows one caption, that each caption is based on its photo's note, and that no caption states a fact that is not in the note.

**Acceptance Scenarios**:

1. **Given** a user has uploaded photos, **When** the user views the photo previews, **Then** each photo has its own note field, labelled separately from the alt text field.
2. **Given** a job with a note on every photo and caption display turned on, **When** the job completes, **Then** each photo's scene shows a caption of at most two lines that is based on that photo's note.
3. **Given** a photo with no note but with alt text, **When** captions are written, **Then** the alt text is used as the basis for that photo's caption.
4. **Given** a user has chosen a caption tone, such as "emotional" or "informative", **When** captions are written, **Then** the captions follow that tone and still contain only facts from the notes, alt text, scenario, or photo.
5. **Given** the text assistance service would receive the user's scenario, notes, or photos, **When** the user has not agreed to the disclosure, **Then** the system does not send them, and it uses each note or alt text as the caption without rewriting it.
6. **Given** the text assistance service is unavailable or fails, **When** the job runs, **Then** the job still completes, using each note or alt text as the caption without rewriting it.
7. **Given** a submitted job that will have captions, **When** the caption drafts are ready, **Then** the job waits in an "awaiting review" state, shows every scene's draft caption next to its photo, and generates nothing until the user confirms.
8. **Given** a job awaiting review, **When** the user edits one or more captions and confirms, **Then** generation starts, and the finished video and subtitle file use the edited captions exactly as typed.

---

### User Story 3 - Subtitle File, Readable On-Screen Text, and Title Cards (Priority: P2)

A user downloads a subtitle file alongside the video, chooses whether captions are drawn into the picture, picks a caption position and look, and optionally adds an opening title and a closing message.

**Why this priority**: The subtitle file makes the video accessible and reusable on other platforms. Title cards and caption styling improve the finished look, but the video is usable without them.

**Independent Test**: Submit a job with captions, a title, and an ending message, with "draw captions into video" turned on. Confirm that the video starts with the title card and ends with the ending card, that captions appear in the chosen position, and that the subtitle file's cue times match the scene changes in the video.

**Acceptance Scenarios**:

1. **Given** a completed job that has captions, **When** the user opens the result, **Then** the user can download a subtitle file in both a plain subtitle format and a styled subtitle format.
2. **Given** "draw captions into video" is turned off, **When** the job completes, **Then** the video has no drawn captions, and the subtitle file is still available.
3. **Given** a title and an ending message are entered, **When** the job completes, **Then** the video begins with a card showing the title and ends with a card showing the ending message.
4. **Given** the caption position is set to "bottom", **When** captions are drawn into the video, **Then** every caption appears in the lower part of the frame and meets the contrast requirement in FR-048.
5. **Given** a job whose scenes include narration text, **When** the job completes, **Then** a subtitle file is provided even if captions are not drawn into the video.

---

### User Story 4 - Background Music (Priority: P2)

A user picks a track from the built-in music library, or uploads their own audio file, and sets its volume. The finished video plays the music from start to end, fading in and out.

**Why this priority**: Music makes photo videos feel finished and is one of the most requested additions, but the video still delivers its story without it.

**Independent Test**: Submit a job that is longer than the chosen library track. Confirm that the music plays for the whole video, repeats where needed, fades in at the start and out at the end, and is at a steady overall loudness. Confirm that the result page shows the track's license notice.

**Acceptance Scenarios**:

1. **Given** a user chooses a library track, **When** the job completes, **Then** the video plays that track from the first frame to the last, with a fade-in and a fade-out.
2. **Given** the track is shorter than the video, **When** the job completes, **Then** the track repeats until the video ends.
3. **Given** the track is longer than the video, **When** the job completes, **Then** the track is cut at the end of the video and fades out before the cut.
4. **Given** a user uploads an audio file in an accepted format and within the size limit, **When** the job completes, **Then** the uploaded audio is used as the background music.
5. **Given** a library track was used, **When** the user views the result, **Then** the track title and its license notice are shown.
6. **Given** a job with no music and no audio in its scenes, **When** the job completes, **Then** the video has no audio track.

---

### User Story 5 - Photo Videos Without a Generation Engine (Priority: P3)

A user who has only photos chooses the "photo slideshow" engine and gets a video quickly, in which each photo slowly zooms or pans. This works even when no generation engine is available on the server.

**Why this priority**: It gives users a fast, low-cost option and lets the whole feature be tested without the generation hardware. The main generation engines remain the primary path.

**Independent Test**: On a server with no generation engine available, submit a photos-only job with five photos and the photo slideshow engine. Confirm that the job succeeds and that each scene shows its photo with a slow zoom or pan.

**Acceptance Scenarios**:

1. **Given** a photos-only job with the photo slideshow engine and motion set to "zoom in", **When** the job completes, **Then** each scene shows its photo slowly zooming in for the scene's full length.
2. **Given** the motion is set to "auto", **When** the job completes, **Then** consecutive scenes use different motions from the supported list.
3. **Given** a scenario-only job, **When** the user chooses the photo slideshow engine, **Then** the system rejects the job before it starts and explains that this engine needs photos.
4. **Given** a scenario-and-photos job with more scenes than photos, **When** the user chooses the photo slideshow engine, **Then** the scenes without their own photo follow the FR-009 rules, using the last photo used.

---

### Edge Cases

- What happens when the chosen transition length is longer than half of a scene? The transition is shortened to half of the shorter of the two scenes it joins.
- What happens when a job has only one scene? No transition is applied, and the scene plays on its own.
- What happens when a generated scene is shorter than requested? The timeline uses the actual length, and captions and music follow the actual timing.
- What happens when title and ending cards push the planned length over 3 minutes? The job is rejected before generation starts, and the message states the limit and the planned length, including the cards (FR-032).
- What happens when a note is too long to fit in two caption lines? A rewritten caption is kept within two lines. When notes are used without rewriting, the text is cut to two lines and ends with an ellipsis. The full note stays visible in the job details.
- What happens to notes on photos that are not used (more photos than scenes, FR-010)? They produce no caption, and they are counted with the unused photos.
- What happens when an uploaded audio file is in an unsupported format or exceeds the size limit? Only that file is rejected, with a message that names the file and the limit, and the rest of the request is not affected.
- What happens when a scene's own audio and the background music both exist? Both are kept. The music plays under the scene audio at the chosen volume.
- What happens when captions contain characters from Korean, English, or both? They are displayed correctly in the video and in the subtitle file.
- What happens when a user changes the language of the interface after captions are written? Captions stay in the language of the user's notes and scenario. They are not translated.
- What happens when a user never confirms a job that is awaiting review? It stays waiting, does not hold a place in the generation queue, and is deleted with its media at the retention deadline (FR-034).
- What happens when a user tries to edit captions on a job that is not awaiting review (queued, running, completed, failed, or expired)? The edit is refused with a message stating that captions can be edited only while the job is awaiting review.
- What happens when a job has no captions (no notes, no alt text, and no scenario text, or captions turned off)? It skips the review step and is queued for generation at once, as in feature 001.
- What happens when a user cancels or deletes a job that is awaiting review? It is allowed, because nothing is being generated.
- What happens when a job is cancelled or deleted? Its subtitle files and uploaded audio are deleted together with its other media.

## Requirements *(mandatory)*

### Functional Requirements

**Timeline and transitions**

- **FR-041**: System MUST place all scenes of a job on one timeline before joining them. The timeline MUST record each scene's start time and length, using each scene's actual generated length when it is shorter than requested. All drawn captions, subtitle cues, and music MUST use these recorded times. Before joining, every scene MUST be brought to the job's frame size and frame rate (this fulfils FR-013). When the transition is "none", the result MUST match the feature 001 result for the same job in scenes, order, and length.
- **FR-042**: Users MUST be able to choose a transition style for a job from: none, fade, fade through black, fade through white, dissolve, slide left, slide right, slide up, slide down, wipe left, circle open, zoom in, and auto. Users MUST be able to set a transition length from 0.1 to 2.0 seconds (default 0.5). The default style is "none". "Auto" MUST cycle through the styles so that consecutive scene changes differ. A transition overlaps the end of one scene with the start of the next, so the final video is shorter than the sum of the scene lengths by the total overlap. A transition MUST NOT be longer than half of either scene it joins.

**Photo slideshow engine**

- **FR-043**: System MUST offer a "photo slideshow" engine that turns each scene's photo into a scene with slow motion: zoom in, zoom out, pan left, pan right, pan up, pan down, or auto. Auto MUST vary the motion between consecutive scenes. Scene length follows the same 5–10 second range as the other engines. This engine MUST be listed and chosen in the same way as the other engines (FR-035), MUST NOT send any data outside the server, and MUST be available without a generation engine. A job with no photos MUST be rejected before generation when this engine is chosen, with a message that this engine needs photos.

**Notes and captions**

- **FR-044**: Each uploaded photo MUST accept an optional note of up to 500 characters, entered separately from its alt text (FR-037). The note MUST be stored with the photo and shown in the job details.
- **FR-045**: Users MUST be able to turn captions on or off for a job (default: off, so that a job with default options behaves as in feature 001). When captions are on, System MUST write one caption for each scene that has a photo note, a photo alt text, or scenario text. A caption MUST be at most two lines. Users MUST be able to choose a caption tone: informative, emotional, humorous, travel diary, or advertisement (default: informative). A caption MUST NOT state a fact that is not in the note, alt text, scenario, or photo. For each photo the basis is, in order of preference: its note, then its alt text, then the photo itself. If captions cannot be written by the text assistance service, System MUST use the note or alt text as the caption without rewriting it, and MUST still complete the job (same principle as FR-006).
- **FR-046**: Before submission, System MUST tell the user, in text, which of their inputs (scenario, notes, photos) would be sent to an external text assistance service, and MUST require explicit agreement. This applies to scene splitting (FR-005) as well as caption writing. System MUST record the time of agreement. Without agreement, System MUST NOT send these inputs, and MUST use paragraph splitting (FR-006) and unrewritten notes or alt text (FR-045).

- **FR-064**: For a job that will have captions, System MUST write the caption drafts in the background after submission (submission still returns at once, FR-024). While drafts are being written, the job is in a new "drafting" state; when they are ready, it moves to a new "awaiting review" state (both extend the status list of FR-017). While awaiting review, System MUST show each scene's draft caption with its photo or scene text, MUST let the user edit each caption within the two-line limit of FR-045, and MUST NOT generate any scene. Generation MUST start only when the user confirms, and the job then joins the generation queue (FR-026). Edited captions MUST be used exactly as typed, without rewriting. A job awaiting review MUST NOT hold a place in the generation queue, MAY be cancelled or deleted (FR-038), and MUST be deleted at its retention deadline (FR-034); confirming MUST NOT extend that deadline. A job without captions MUST skip this state. Captions cannot be edited in any other state.

**Subtitles and on-screen text**

- **FR-047**: For every completed job that has captions, System MUST provide a subtitle file for download in a plain subtitle format and in a styled subtitle format. Users MUST be able to choose whether captions are also drawn into the video (default: not drawn). Any video that contains narration text MUST have a subtitle file (constitution III). Each cue MUST start and end at the scene times recorded in FR-041, adjusted to the midpoint of any transition.
- **FR-048**: Users MUST be able to choose the caption position from 9 screen positions: top_left, top_center, top_right, middle_left, middle_center, middle_right, bottom_left, bottom_center, bottom_right (and none). Legacy options top, bottom, and automatic map to top_center and bottom_center. In addition, users can specify text size and text color. Uploaded photo descriptions (alt text / note) are automatically extracted as captions for each scene. Drawn captions MUST have an outline and 60% opaque background box (BorderStyle=3) using bundled NanumGothic so that text contrast against the picture is at least 4.5:1. Captions MUST display Korean and English text correctly.
- **FR-049**: Users MUST be able to add an optional opening title and an optional closing message. Each appears as its own card scene at the start or end of the video. Card scenes count toward the planned length and the 3-minute limit (FR-032).

**Background music and audio**

- **FR-050**: Users MUST be able to choose background music from a built-in library, upload an audio file (MP3, WAV, or M4A, up to 30 MB), or choose no music (default). Users MUST be able to set the music volume from 0% to 100% (default 30%). Music MUST play for the full length of the video, repeat when shorter, and fade in at the start and out at the end. For a library track, the result page MUST show the track title and its license notice. Uploaded audio MUST be deleted with the job's other media under FR-034 and FR-038.
- **FR-051**: When a video contains any audio, its overall loudness MUST be brought to one consistent target level. When a job has no music and none of its scenes has audio, the video MUST NOT contain an audio track.

### Key Entities *(include if feature involves data)*

- **Photo (Source Image)** *(extended)*: Adds an optional note of up to 500 characters, separate from the alt text.
- **Job** *(extended)*: Adds the "drafting" and "awaiting review" states between submission and generation for jobs with captions, and the time the user confirmed the review.
- **Scene** *(extended)*: Adds its caption (and whether the user edited it during review), its narration text (if any), its transition style (or "use the job default"), its motion (for the photo slideshow engine), its start time and length on the timeline, and its kind: regular scene, title card, or ending card.
- **Render Options** *(new, part of the Job)*: Transition style and length, motion, caption tone, whether captions are drawn into the video, caption style (position, size, color), title text, ending text, and background music choice and volume. These can change the finished look without changing what each scene shows.
- **Music Track** *(new)*: An entry in the built-in library, with a title, a mood, a length, and a license notice. An uploaded audio file is treated as a private track that belongs to one job.
- **Subtitle File** *(new)*: The caption cues of one completed job, available in a plain format and a styled format. It belongs to the job and is deleted with it.
- **Text Assistance Agreement** *(new, part of the Job)*: The time the user agreed to send inputs to the external text assistance service, or its absence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-009**: A user can create a video with transitions, captions written from photo notes, and background music from ten photos, and the job succeeds on a server that has no generation engine available, using the photo slideshow engine.
- **SC-010**: Every subtitle cue starts and ends within 0.1 seconds of the matching scene change in the video.
- **SC-011**: In a review of at least 50 generated captions, none states a fact that is absent from its note, alt text, scenario, or photo, and at least 90% are rated by reviewers as matching the chosen tone.
- **SC-012**: Adding transitions, captions, and music to a job increases its total completion time by no more than 10% compared with the same job without them. Time spent waiting for the user's review is not counted.
- **SC-015**: For a job with up to 20 photos, caption drafts are ready for review within 1 minute of submission.
- **SC-013**: 90% of users who type notes on their photos can find and turn on captions, choose a transition, and add music on their first attempt, without reading documentation.
- **SC-014**: Users can complete every new choice in this feature (notes, transition, caption options, title cards, music, agreement) using only a keyboard.

## Assumptions

- **Scope**: This feature covers Release 2 of the product specification. Spoken narration from text, automatic scene length from narration, music ducking under narration, word-by-word highlighted captions, aspect-ratio presets, storyboard editing beyond captions (reordering, deleting, or changing scene descriptions, lengths, or transitions during review), editing after generation, re-generating single shots, templates, photo ordering by capture time, and beat-matched transitions are out of scope. They are planned for Release 3.
- **Narration text**: Captions are written in this release. Narration text may also be written and stored with each scene for later use, but no spoken audio is produced in this release.
- **Defaults keep feature 001 behavior**: With no transition, no captions, no titles, and no music, a job produces the same result as in feature 001.
- **Caption language**: Captions are written in the language of the user's notes and scenario. Translation is out of scope.
- **Caption length**: Two lines of up to about 42 characters each is the target for readability on common screen sizes.
- **Subtitle formats**: The plain format is SubRip (.srt) and the styled format is Advanced SubStation Alpha (.ass), because both are widely supported by video players and platforms.
- **Music library**: The server ships with a small curated set of tracks whose licenses allow use in the users' videos. Each track's license notice is stored with it. Generating music automatically is out of scope.
- **Scene audio**: Audio produced by a generation engine is kept and mixed under the background music, as in feature 001, which passes engine audio through unchanged.
- **Text assistance service**: The external service used for scene splitting (FR-005) is also used for captions. It is treated as an external service under FR-046 in the same way that a cloud engine is treated under FR-036.
- **Retention and ownership**: All new media (subtitle files, uploaded audio) follow the 2-day retention rule (FR-034), the delete rule (FR-038), and the ownership rule (FR-031).
- **Performance and accessibility**: The performance budgets and the accessibility level in the project constitution apply. Joining scenes with transitions, captions, and music does not require the generation hardware.
