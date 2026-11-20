# Feature Specification: Movie Video Generation from Scenario and Photos

**Feature Branch**: `001-movie-video-generation`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Movie Maker: a system where users create an MP4 video from a text scenario, from still photos, or from both."

## Clarifications

### Session 2026-11-20

- Q: Who should be able to see a job and its finished video in the first release? → A: Login required; each user sees only their own jobs.
- Q: What is the longest finished video a single job may produce? → A: 3 minutes maximum.
- Q: When one shot fails to generate, should the system retry that shot before failing the job? → A: Retry the failed shot once automatically; fail the job only if the retry also fails.
- Q: How many users are expected to be using the service at the same time in the first release? → A: Up to about 5 users at the same time.
- Q: How long should a user's uploaded photos and generated videos be kept before the system deletes them automatically? → A: Delete automatically 2 days after the job is created.
- Q: Which video engines should a user be able to choose for each job? → A: LTX-2.3 (local GPU, default) or Gemini Omni 1.2 Flash (cloud), selected in the UI. Recorded from user direction on 2026-11-20.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a Video from a Text Scenario (Priority: P1)

A user writes a short text scenario describing a story or scene sequence, submits it with output options, and receives a finished MP4 video that follows the scenario.

**Why this priority**: This is the core promise of the product. A video generated from text alone is the most basic complete value path, and it must work before any other mode.

**Independent Test**: Submit a scenario with no photos. Wait for the job to finish. Download the result and confirm it is a playable MP4 whose scenes match the scenario's paragraphs.

**Acceptance Scenarios**:

1. **Given** a user has entered a multi-paragraph scenario and no photos, **When** the user submits the job, **Then** the system accepts the job and shows it as queued or running.
2. **Given** a submitted scenario-only job completes, **When** the user opens the result, **Then** a playable MP4 is available, and it contains one or more shots, one for each scene the scenario was split into.
3. **Given** the scenario cannot be split by the advanced splitting service, **When** the job runs, **Then** the job still completes using a paragraph-based split, and the user is not required to take any action.

---

### User Story 2 - Create a Video from Photos Only (Priority: P1)

A user uploads one or more photos without any text and receives an MP4 in which each photo appears as a moving scene.

**Why this priority**: Photo-only generation is the simplest way to turn existing images into video and is independently valuable. It can ship alongside Story 1.

**Independent Test**: Upload three photos with no scenario. Wait for the job to finish. Confirm the result has three shots, each derived from one photo, and that each shot shows motion.

**Acceptance Scenarios**:

1. **Given** a user uploads three valid photos and no scenario, **When** the user submits the job, **Then** the job runs in photo-only mode with one shot per photo.
2. **Given** a photo-only job completes, **When** the user views the shot list, **Then** each shot is linked to the photo it came from.

---

### User Story 3 - Create a Video from Both Scenario and Photos (Priority: P2)

A user supplies a scenario and photos together. Each photo is matched to a scene, so the video follows the story and uses the user's own images.

**Why this priority**: This combined mode gives the most control and the best results. It depends on the two single-input stories being in place.

**Independent Test**: Submit a scenario with four paragraphs and two photos. Confirm the first photo is used for the first scene, the second photo for the second scene, and the remaining scenes still produce shots.

**Acceptance Scenarios**:

1. **Given** a scenario has more scenes than photos, **When** the job runs, **Then** scenes without a photo use the last available photo, or the last frame of the preceding shot, so that every scene still gets a shot.
2. **Given** a scenario has fewer scenes than photos, **When** the job runs, **Then** the extra photos are reported to the user as unused, and the job still completes.

---

### User Story 4 - Track Progress and Retrieve Results (Priority: P2)

A user who submits a job sees its status and progress update while it runs, and can open or download the result from a job list once it finishes.

**Why this priority**: Generation takes minutes to tens of minutes. Without visible progress, users cannot tell whether the system is working, and the feature is not usable.

**Independent Test**: Submit a job and keep the page open. Confirm progress moves from 0 to 100 with a message of at most 120 characters at each stage, and that the finished video appears in the job list and can be downloaded.

**Acceptance Scenarios**:

1. **Given** a job is running, **When** the user views its page, **Then** the status, progress percentage, and current stage message are shown, and they update without a manual page refresh.
2. **Given** a job has succeeded, **When** the user opens the job list, **Then** the job appears with status "succeeded" and a download action for its video.
3. **Given** a job has failed, **When** the user views it, **Then** the status is "failed" with a message that explains the failure in plain language.

---

### User Story 5 - Adjust Output Options (Priority: P3)

A user can choose the resolution, the length of each shot, the frame rate, and whether consecutive shots flow continuously, before submitting a job.

**Why this priority**: Sensible defaults let every user succeed without changing anything. Advanced options serve power users and can come later.

**Independent Test**: Submit the same scenario twice with different resolutions and shot lengths. Confirm each result matches the requested settings within normal encoding tolerance.

**Acceptance Scenarios**:

1. **Given** a user has not changed any options, **When** the user submits a job, **Then** the defaults apply: 832 by 480 pixels, 5 seconds per shot, 16 frames per second, and continuous flow between shots.
2. **Given** a user sets a custom resolution and shot length, **When** the job completes, **Then** the final video uses that resolution, and each shot lasts the requested length within one second.

---

### User Story 6 - Choose a Video Engine per Job (Priority: P2)

A user chooses the video engine for each job: the local LTX-2.3 engine (the default) or the cloud Gemini Omni 1.2 Flash engine. Before a cloud job is submitted, the user is told in text that the scenario and photos will be sent to the cloud provider, and must confirm.

**Why this priority**: The user asked for an explicit engine choice. The cloud option sends personal data outside the service, so the disclosure must ship with it.

**Independent Test**: Open the job form with the keyboard only. LTX-2.3 is preselected. Select Gemini, read the disclosure, and confirm that submission stays blocked until the confirmation is checked. Submit with the local engine and confirm that no disclosure is required.

**Acceptance Scenarios**:

1. **Given** a user opens the job form, **When** the form loads, **Then** LTX-2.3 is preselected and each engine option has a text label.
2. **Given** a user selects Gemini Omni 1.2 Flash, **When** the user tries to submit without confirming, **Then** submission is blocked, and the disclosure text states that the scenario and photos will be sent to Google.
3. **Given** a cloud engine is not configured on the server, **When** the user views the engine choice, **Then** that option is shown as unavailable, with the reason in text.

---

### Edge Cases

- What happens when a job is submitted with no scenario and no photos? The submission is rejected with a clear message that at least one input is required.
- What happens when an uploaded file is not a supported image type (JPG, PNG, WebP)? The file is rejected with a message naming the file and the accepted types. Other files in the same submission are not affected.
- What happens when a single photo exceeds 20 MB? The file is rejected with a message stating the size limit.
- What happens when one shot fails to generate? The system retries that shot once automatically. If the retry also fails, the job is marked failed and reports which shot failed. The user can resubmit without re-entering inputs.
- What happens when a job runs longer than the configured time limit? The job is stopped, marked failed with a timeout message, and does not block other jobs.
- What happens when several jobs are submitted at once? Jobs are queued and run in order. Each job reports "queued" until it starts, and users are told their position if one is available.
- What happens when a user requests a video before the job finishes? The video is not offered for download until the job succeeds, and the page says the video is not ready yet.
- What happens when a scenario or photo set would produce a video longer than 3 minutes? The job is rejected before generation starts, with a message stating the 3-minute limit and the planned length. No part of the input is silently dropped.
- What happens when the user closes the page during generation? The job continues. The user can see its status when they return.
- What happens when a logged-in user opens another user's job or video link? The system responds as if the job does not exist.

## Requirements *(mandatory)*

### Functional Requirements

**Job creation**

- **FR-001**: System MUST let a user create a video job by providing a scenario text, one or more photos, or both.
- **FR-002**: System MUST reject a job that has neither a scenario nor any photos, with a clear message.
- **FR-003**: System MUST accept photos in JPG, PNG, and WebP formats, up to 20 MB each.
- **FR-004**: System MUST accept between 1 and 100 photos per job. Requests with more photos MUST be rejected with a message stating the limit.

**Scenario splitting**

- **FR-005**: System MUST split a scenario into an ordered list of scenes, where each scene has a visual description and a duration.
- **FR-006**: If advanced splitting is unavailable or fails, System MUST fall back to splitting by paragraph, and MUST still complete the job.
- **FR-007**: System MUST NOT silently drop any part of the scenario.

**Photo-to-scene mapping**

- **FR-008**: System MUST assign the nth photo to the nth scene.
- **FR-009**: When there are more scenes than photos, System MUST continue each remaining scene from the last photo used when chain_frames is off, or from the final frame of the preceding shot when chain_frames is on.
- **FR-010**: When there are more photos than scenes, System MUST report the unused photos to the user and complete the job.
- **FR-011**: When a job has photos only, System MUST create one shot per photo, using a default motion description.

**Video generation**

- **FR-012**: System MUST generate one video shot per scene, and MUST join the shots in order into one final MP4 file.
- **FR-013**: System MUST normalize all shots to the same resolution and frame rate before joining them.
- **FR-014**: System MUST let the user set resolution, seconds per shot, and frame rate, and MUST apply the defaults in Story 5 when they are not set.
- **FR-015**: System MUST let the user choose whether each shot continues from the final frame of the previous shot.
- **FR-016**: System MUST allow the video generation engine to be changed through configuration, without changes to the application code.
- **FR-035**: System MUST let the user choose the video engine for each job from the engines currently enabled. The engines offered are LTX-2.3 (local, default) and Gemini Omni 1.2 Flash (cloud). The choice MUST be a keyboard-operable control, and each option MUST have a text label.
- **FR-036**: Before a job that uses a cloud engine is submitted, System MUST tell the user, in text, that the scenario and uploaded photos will be sent to that provider. System MUST require explicit confirmation, and MUST record the confirmation with the job.

**Progress and status**

- **FR-017**: System MUST track each job's status as one of: queued, running, succeeded, failed, or expired. A job becomes expired when its media is deleted under FR-034.
- **FR-018**: System MUST report each job's progress as a whole-number percentage from 0 to 100, and a short message describing the current stage.
- **FR-019**: System MUST push progress updates to the user's open page without requiring a manual refresh.
- **FR-020**: System MUST keep a job's progress and status available after the user leaves and returns.

**Results**

- **FR-021**: System MUST make the final MP4 available for download once a job succeeds.
- **FR-022**: System MUST list each job's shots, showing the scene it came from and its status.
- **FR-023**: System MUST show a job list containing all of the user's jobs, most recent first.

**Reliability**

- **FR-024**: System MUST run generation in the background so that submitting a job returns immediately with a job identifier.
- **FR-025**: System MUST enforce a configurable time limit per job, and mark jobs that exceed it as failed.
- **FR-026**: System MUST process one generation job at a time per generation resource, and MUST queue additional jobs.
- **FR-027**: System MUST report which shot failed when a job fails, so the user knows what to change.
- **FR-033**: When a shot fails to generate, System MUST retry that shot once automatically. System MUST mark the job failed only if the retry also fails.

**Data retention**

- **FR-034**: System MUST automatically and permanently delete a job's uploaded photos, shots, and final video 2 days after the job is created.

**Accessibility**

- **FR-028**: All job creation, progress, and result functions MUST be fully usable with a keyboard alone.
- **FR-029**: All error messages MUST be shown as text, and MUST NOT rely on color alone.
- **FR-037**: Each uploaded photo MUST accept an optional, user-entered alt text of up to 500 characters, and the alt text MUST be stored with the photo.
- **FR-038**: A user MUST be able to delete one of their own jobs and its media before the retention deadline. A job that is queued or running cannot be deleted.

**Access and ownership**

- **FR-030**: System MUST require a user to log in before creating, viewing, or downloading any job.
- **FR-031**: System MUST show each user only the jobs and videos they created. System MUST NOT reveal another user's jobs, videos, or their existence through any screen, list, or link.

**Length limits**

- **FR-032**: System MUST reject a job before generation starts when its planned final video would exceed 3 minutes. The planned length is the number of shots multiplied by seconds per shot. The rejection MUST state the limit and the planned length.

### Key Entities *(include if feature involves data)*

- **Job**: A single request to create a video. Has an identifier, a status, a progress percentage, a stage message, the chosen output options, the input mode (scenario only, photos only, or both), and a link to its final video once complete.
- **Scene**: One part of a scenario, in order. Has a visual description, a duration, and optionally an associated photo.
- **Shot**: The generated clip for one scene. Has its own status, its source scene, and its source photo if any. Shots combine in order to form the final video.
- **Photo (Source Image)**: An image uploaded by the user, with a file type, size, and optional alt text. It belongs to one job.
- **Output Options**: The resolution, seconds per shot, frame rate, and continuity setting for a job.
- **User**: A person with a login account. Owns the jobs they create, and can see only those jobs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from starting a new job to seeing it in progress in under 1 minute, without reading documentation.
- **SC-002**: For a valid submission, the user receives a playable video, and at least 95% of such jobs complete without failure under normal operating conditions, defined as at most 5 concurrent users, one available generation worker, and no outage of the selected engine.
- **SC-003**: During generation, the user sees progress updates at least every 10 seconds, so the page never appears frozen.
- **SC-004**: Once the upload has finished, the user receives an acknowledgment of the job in under 1 second, even when generation takes many minutes.
- **SC-005**: Users can complete every job-creation, progress, and download action using only a keyboard.
- **SC-006**: 90% of users can create their first video on the first attempt with the default options.
- **SC-007**: When a job fails, 90% of users can state the cause from the message shown, without contacting support.
- **SC-008**: Users can choose a different video generation engine through configuration, and the change takes effect without application changes.

## Assumptions

- **Users and access**: The first release requires users to log in. Each user creates, views, and downloads only their own jobs and videos. The sign-in method is a planning decision.
- **Scale**: The first release supports up to about 5 users at the same time. Jobs run one at a time per generation resource, and additional jobs are queued (FR-026).
- **Generation time**: Generating a video takes minutes to tens of minutes. Users are expected to wait and return to the job list; they are not expected to keep the page open.
- **Shot length**: Each generated shot lasts between 5 and 10 seconds. The seconds-per-shot option is interpreted within that range.
- **Output format**: The only output format is MP4.
- **Narration and subtitles**: Automatic narration, subtitles, and background music are out of scope for this release. They are planned for a later phase.
- **Scene splitting**: Advanced splitting is an improvement on the basic paragraph split. The basic split is always available and is the fallback.
- **Default motion**: When only photos are given, every shot uses one fixed motion instruction: "Slow, steady camera push-in; the subject moves naturally; no scene change."
- **Retention**: Uploaded photos and generated videos are deleted automatically 2 days after the job is created (FR-034).
- **Content**: Scenario content and uploaded photos are the user's responsibility. Content moderation is out of scope for this release.
- **Video engines**: Two engines are offered: LTX-2.3 (local GPU, the default) and Gemini Omni 1.2 Flash (cloud). The user chooses one for each job (FR-035). Licensing and cost are planning decisions. Any engine must meet the requirements in this document. Engines may produce audio; this release passes it through unchanged and does not add narration. Automatic fallback from the local engine to the cloud engine is out of scope for this release; the user chooses the engine for each job.
- **Performance and accessibility**: The targets in the project constitution apply to this feature, including the performance budgets and the accessibility level.
