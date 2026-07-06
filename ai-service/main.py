from fastapi import Depends, FastAPI, Header, UploadFile, File, HTTPException

from pipeline import analyze_image
from typing import Annotated, Optional
from PIL import Image, UnidentifiedImageError

import io
import tempfile
import os

# No CORSMiddleware here, deliberately: this service is called
# server-to-server, only ever from the application backend
# (backend/app/services/ai_client.py) — never from a browser. Without
# CORS headers, a browser page attempting to call this directly gets
# blocked by same-origin policy on the response; adding permissive CORS
# here would be actively wrong, since it would be the one thing that lets
# a browser read this service's responses cross-origin.
app = FastAPI(
    title="ClaimSight AI Service",
    description="AI-powered vehicle damage analysis service",
    version="1.1.0"
)


ALLOWED_CONTENT_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp"
]

# Generous for a phone photo, small next to a deliberately oversized upload.
MAX_IMAGE_BYTES = 10 * 1024 * 1024

# Optional defense-in-depth: if set, every /analyze* call must present this
# exact value as X-Internal-Service-Token. Unset (the local-dev default)
# means no check is enforced — network isolation (this service not being
# reachable from outside the backend) is the primary control; this is a
# second layer for deployments where that isolation can't be guaranteed.
_INTERNAL_SERVICE_TOKEN = os.environ.get("AI_SERVICE_SHARED_SECRET", "")


def require_internal_caller(
    x_internal_service_token: Annotated[Optional[str], Header()] = None
) -> None:
    if _INTERNAL_SERVICE_TOKEN and x_internal_service_token != _INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden.")


# ==================================================
# BASIC ROUTES
# ==================================================

@app.get("/")
def root():

    return {
        "service": "ClaimSight AI Service",
        "status": "running",
        "version": "1.1.0"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ==================================================
# MERGE RESULTS FROM MULTIPLE IMAGES
# ==================================================
#
# This service's response contract carries no pricing fields. Cost
# estimation is vehicle-category-aware business logic that lives in the
# backend's services/cost_model layer, which needs claimant-submitted
# vehicle metadata this service never sees.

def _is_better_observation(candidate, current):

    # --------------------------------------------------
    # REPRESENTATIVE-SELECTION RULE
    # --------------------------------------------------
    #
    # 1. Accepted (trusted) observations always outrank Review Required
    #    ones — a confirmed reading must never be displaced by an
    #    uncertain one, regardless of its damage_percentage.
    #
    # 2. Within the same status tier, the higher damage_percentage wins
    #    ("worst damage seen" is the conservative choice for a claim).
    #    Within "Accepted" results, damage_percentage always comes from
    #    the trusted mask (see pipeline.py), so it's a meaningful,
    #    comparable number across different photos of the same part.
    #
    # The winner is kept as a COMPLETE, untouched observation — its
    # severity, damage_percentage, damage_confidence, part_confidence,
    # status and recommended_action always come from the same image's
    # result. They are never reassembled field-by-field from different
    # images, which would produce a contradictory merged result (e.g. a
    # damage percentage paired with a confidence score that never
    # actually supported it).

    candidate_accepted = candidate["status"] == "Accepted"
    current_accepted = current["status"] == "Accepted"

    if candidate_accepted != current_accepted:
        return candidate_accepted

    return (
        candidate["damage_percentage"]
        >
        current["damage_percentage"]
    )


def merge_analysis_results(image_results):

    merged_parts = {}


    for image_result in image_results:

        filename = image_result["filename"]

        analysis = image_result["analysis"]


        for part in analysis["damaged_parts"]:

            part_name = part["part"]


            # --------------------------------------
            # FIRST TIME THIS PART IS SEEN
            # --------------------------------------

            if part_name not in merged_parts:

                merged_parts[part_name] = {

                    "representative":
                        dict(part),

                    "detected_in_images": [
                        filename
                    ],

                    "max_damage_confidence_seen":
                        part["damage_confidence"],

                    "max_part_confidence_seen":
                        part["part_confidence"],
                }

                continue


            existing = merged_parts[part_name]


            # --------------------------------------
            # ADD IMAGE REFERENCE + AGGREGATE METADATA
            # --------------------------------------
            # These accumulate across every observation of this part,
            # independent of which observation ends up representative.

            existing[
                "detected_in_images"
            ].append(
                filename
            )

            existing[
                "max_damage_confidence_seen"
            ] = max(

                existing[
                    "max_damage_confidence_seen"
                ],

                part[
                    "damage_confidence"
                ]
            )

            existing[
                "max_part_confidence_seen"
            ] = max(

                existing[
                    "max_part_confidence_seen"
                ],

                part[
                    "part_confidence"
                ]
            )


            # --------------------------------------
            # REPLACE REPRESENTATIVE AS A WHOLE UNIT
            # --------------------------------------

            if _is_better_observation(
                part,
                existing["representative"]
            ):

                existing[
                    "representative"
                ] = dict(part)


    merged_list = []


    for part_name, data in merged_parts.items():

        merged_part = dict(
            data["representative"]
        )

        merged_part[
            "detected_in_images"
        ] = data["detected_in_images"]

        merged_part[
            "observation_count"
        ] = len(data["detected_in_images"])

        merged_part[
            "max_damage_confidence_seen"
        ] = data["max_damage_confidence_seen"]

        merged_part[
            "max_part_confidence_seen"
        ] = data["max_part_confidence_seen"]

        merged_list.append(merged_part)


    # ==================================================
    # CLAIM SUMMARY
    # ==================================================

    accepted = 0
    review_required = 0


    for part in merged_list:

        if part["status"] == "Accepted":
            accepted += 1

        else:
            review_required += 1


    return {

        "damaged_parts":
            merged_list,

        "summary": {

            "total_parts":
                len(merged_list),

            "accepted":
                accepted,

            "review_required":
                review_required
        }
    }


# ==================================================
# SINGLE IMAGE ANALYSIS
# ==================================================

@app.post("/analyze", dependencies=[Depends(require_internal_caller)])
async def analyze(
    image: Annotated[UploadFile, File()]
):

    if image.content_type not in ALLOWED_CONTENT_TYPES:

        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "unsupported_file_type",
                "message": "Only JPEG, PNG and WebP images are supported.",
                "invalid_filenames": [image.filename],
            },
        )


    suffix = os.path.splitext(
        image.filename or ""
    )[1] or ".jpg"


    temp_path = None


    try:

        content = await image.read()

        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "file_too_large",
                    "message": f"{image.filename}: exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)}MB limit.",
                    "invalid_filenames": [image.filename],
                },
            )

        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "corrupted_image",
                    "message": f"{image.filename}: could not be read as an image.",
                    "invalid_filenames": [image.filename],
                },
            )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp_file:

            temp_file.write(content)

            temp_path = temp_file.name


        result = analyze_image(
            temp_path
        )


    except HTTPException:

        # Structured rejections raised above (file_too_large, corrupted_image)
        # must pass through untouched, never re-wrapped as a generic 500 by
        # the `except Exception` clause below.
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(error)}"
        )


    finally:

        if (
            temp_path
            and os.path.exists(temp_path)
        ):

            os.remove(temp_path)


    # Raised outside the try/except above so this structured rejection
    # is never re-wrapped as a generic 500 by the except clause.
    if not result["vehicle_detected"]:

        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "vehicle_not_detected",
                "message": (
                    "This image does not appear to contain a vehicle."
                ),
                "invalid_filenames": [image.filename],
            },
        )


    return {

        "success": True,

        "filename":
            image.filename,

        "analysis":
            result
    }


# ==================================================
# MULTI-IMAGE CLAIM ANALYSIS
# ==================================================

@app.post("/analyze-claim", dependencies=[Depends(require_internal_caller)])
async def analyze_claim(
    images: Annotated[
        list[UploadFile],
        File(description="Upload multiple vehicle images")
    ]
):

    if len(images) == 0:

        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "unsupported_file_type",
                "message": "At least one image is required.",
                "invalid_filenames": [],
            },
        )


    if len(images) > 10:

        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "too_many_files",
                "message": "Maximum 10 images allowed per claim.",
                "invalid_filenames": [],
            },
        )


    image_results = []

    # Filenames that failed the vehicle-presence gate (see
    # pipeline.check_vehicle_presence) or the corrupted-image decode check
    # below. Each collected across the whole batch rather than failing on
    # the first one, so the caller finds out about every bad image in one
    # response instead of fixing them one at a time.
    invalid_filenames = []
    corrupted_filenames = []


    for image in images:


        if image.content_type not in ALLOWED_CONTENT_TYPES:

            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "unsupported_file_type",
                    "message": f"{image.filename}: unsupported file type.",
                    "invalid_filenames": [image.filename],
                },
            )


        suffix = os.path.splitext(
            image.filename or ""
        )[1] or ".jpg"


        temp_path = None


        try:

            content = await image.read()

            if len(content) > MAX_IMAGE_BYTES:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_code": "file_too_large",
                        "message": (
                            f"{image.filename}: exceeds the "
                            f"{MAX_IMAGE_BYTES // (1024 * 1024)}MB limit."
                        ),
                        "invalid_filenames": [image.filename],
                    },
                )

            try:
                with Image.open(io.BytesIO(content)) as img:
                    img.verify()
            except (UnidentifiedImageError, OSError, ValueError):
                # Recorded, never silently dropped — same whole-batch
                # accumulation as the vehicle-presence check below.
                corrupted_filenames.append(image.filename)
                continue


            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix
            ) as temp_file:

                temp_file.write(content)

                temp_path = temp_file.name


            analysis = analyze_image(
                temp_path
            )


        except HTTPException:

            # file_too_large above must pass through untouched, never
            # re-wrapped as a generic 500 by the except clause below.
            raise

        except Exception as error:

            raise HTTPException(

                status_code=500,

                detail=(
                    f"Failed to analyze "
                    f"{image.filename}: {str(error)}"
                )
            )


        finally:

            if (
                temp_path
                and os.path.exists(temp_path)
            ):

                os.remove(temp_path)


        if not analysis["vehicle_detected"]:

            # Recorded, never silently dropped — the whole claim is
            # rejected below once every image has been checked.
            invalid_filenames.append(image.filename)
            continue


        image_results.append({

            "filename":
                image.filename,

            "analysis":
                analysis
        })


    if corrupted_filenames:

        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "corrupted_image",
                "message": "One or more images could not be read.",
                "invalid_filenames": corrupted_filenames,
            },
        )


    if invalid_filenames:

        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "vehicle_not_detected",
                "message": (
                    "One or more images do not appear to contain a "
                    "vehicle."
                ),
                "invalid_filenames": invalid_filenames,
            },
        )


    # ----------------------------------------------
    # MERGE ALL IMAGE RESULTS
    # ----------------------------------------------

    claim_analysis = merge_analysis_results(
        image_results
    )


    return {

        "success":
            True,

        "images_processed":
            len(image_results),

        "claim_analysis":
            claim_analysis,

        "individual_results":
            image_results
    }
