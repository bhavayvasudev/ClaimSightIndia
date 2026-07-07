from ultralytics import YOLO
import numpy as np
import cv2

import logging
import time

logger = logging.getLogger("ai_service.pipeline")


PARTS_CONF = 0.10
DAMAGE_CONF = 0.08
TRUSTED_DAMAGE_CONF = 0.18

MIN_DAMAGE_IN_PART = 0.10
MIN_PART_DAMAGED = 0.02

# Generic-object presence gate, run before the two domain-specific models
# below. car_parts_best.pt / damage_seg_50_best.pt only know car parts and
# damage textures — neither has a "not a vehicle" class, so a person/food/
# room photo silently produces zero detections from them (indistinguishable
# from a genuine damage-free car). yolo11n.pt is stock COCO-pretrained and
# already ships in this directory unused; its "car"/"truck"/"bus"/
# "motorcycle" classes are a cheap, real presence check for exactly this
# gap. "bicycle"/"train"/"boat"/"airplane" are deliberately excluded — none
# of them are a motor vehicle this system prices or inspects.
VEHICLE_PRESENCE_CLASSES = {"car", "truck", "bus", "motorcycle"}
VEHICLE_PRESENCE_CONF = 0.35


# Load once when service starts (import time). The timestamps below are
# the ground truth for "did a request hit a fresh process": a Space
# restart/rebuild re-runs this block, so models_loaded appears again in
# the logs and MODELS_LOADED_AT resets.
logger.info("model_load_started")
_model_load_start = time.perf_counter()

vehicle_presence_model = YOLO(
    "yolo11n.pt"
)

parts_model = YOLO(
    "models/car_parts_best.pt"
)

damage_model = YOLO(
    "models/damage_seg_50_best.pt"
)

MODEL_LOAD_DURATION_MS = int((time.perf_counter() - _model_load_start) * 1000)
MODELS_LOADED_AT = time.time()
logger.info("models_loaded duration_ms=%d", MODEL_LOAD_DURATION_MS)


def check_vehicle_presence(image_path):
    """Cheap pre-check: does this image contain a class we treat as a
    motor vehicle, at all? Returns (detected, best_confidence). Never
    inspects damage/parts — this is a presence gate, not a quality one."""

    result = vehicle_presence_model.predict(
        image_path,
        conf=VEHICLE_PRESENCE_CONF,
        verbose=False
    )[0]

    best_confidence = 0.0
    detected = False

    for box in result.boxes:
        class_name = vehicle_presence_model.names[int(box.cls[0])]

        if class_name in VEHICLE_PRESENCE_CLASSES:
            detected = True
            best_confidence = max(best_confidence, float(box.conf[0]))

    return detected, round(best_confidence, 3)


def get_severity(part_name, damage_percentage):

    name = part_name.lower()

    if any(x in name for x in [
        "headlight",
        "rear light",
        "tail light"
    ]):

        if damage_percentage < 10:
            return "Minor"

        elif damage_percentage < 25:
            return "Moderate"

        return "Severe"


    elif any(x in name for x in [
        "hood",
        "door",
        "fender",
        "bonnet",
        "boot"
    ]):

        if damage_percentage < 12:
            return "Minor"

        elif damage_percentage < 35:
            return "Moderate"

        return "Severe"


    elif "bumper" in name:

        if damage_percentage < 15:
            return "Minor"

        elif damage_percentage < 40:
            return "Moderate"

        return "Severe"


    else:

        if damage_percentage < 10:
            return "Minor"

        elif damage_percentage < 30:
            return "Moderate"

        return "Severe"


def get_status(
    part_confidence,
    damage_confidence,
    has_trusted_damage
):

    if not has_trusted_damage:
        return "Review Required"

    if part_confidence < 0.30:
        return "Review Required"

    if damage_confidence < TRUSTED_DAMAGE_CONF:
        return "Review Required"

    return "Accepted"


def get_repair_action(
    part_name,
    severity,
    status
):

    name = part_name.lower()

    if (
        status == "Review Required"
        or severity == "Uncertain"
    ):
        return "Manual Inspection"


    if any(x in name for x in [
        "headlight",
        "rear light",
        "tail light"
    ]):

        if severity == "Minor":
            return "Repair"

        return "Replace"


    if "bumper" in name:

        if severity in [
            "Minor",
            "Moderate"
        ]:
            return "Repair"

        return "Replace"


    if any(x in name for x in [
        "hood",
        "bonnet",
        "door",
        "fender",
        "boot"
    ]):

        if severity == "Minor":
            return "Repair"

        elif severity == "Moderate":
            return "Repair + Repaint"

        return "Replace / Major Repair"


    if severity == "Minor":
        return "Repair"

    elif severity == "Moderate":
        return "Repair + Repaint"

    return "Replace / Major Repair"


# ==================================================
# MAIN ANALYSIS FUNCTION
# ==================================================
#
# NOTE: cost estimation is deliberately NOT part of this service. The
# ai-service is responsible only for detection, segmentation, matching,
# severity, confidence, status and recommended_action — pricing is
# vehicle-category-aware business logic owned by the backend's
# services/cost_model layer, which consumes this service's output plus
# claimant-submitted vehicle metadata. See docs on the pricing boundary.

def analyze_image(image_path):

    vehicle_detected, vehicle_confidence = check_vehicle_presence(
        image_path
    )

    if not vehicle_detected:

        # Deliberately never reaches parts_model/damage_model below —
        # the presence gate runs, and this returns, before either of the
        # expensive models sees the image.
        return {
            "vehicle_detected": False,
            "vehicle_confidence": vehicle_confidence,
            "damage_detected": False,
            "damaged_parts": [],
            "summary": {
                "total_parts": 0,
                "accepted": 0,
                "review_required": 0
            }
        }


    parts_result = parts_model.predict(
        image_path,
        conf=PARTS_CONF,
        verbose=False
    )[0]


    damage_result = damage_model.predict(
        image_path,
        conf=DAMAGE_CONF,
        verbose=False
    )[0]


    if damage_result.masks is None:

        return {
            "vehicle_detected": True,
            "vehicle_confidence": vehicle_confidence,
            "damage_detected": False,
            "damaged_parts": [],
            "summary": {
                "total_parts": 0,
                "accepted": 0,
                "review_required": 0
            }
        }


    image_height, image_width = (
        parts_result.orig_shape
    )


    damage_masks = (
        damage_result
        .masks
        .data
        .cpu()
        .numpy()
    )


    # ----------------------------------------------
    # PART DETECTIONS
    # ----------------------------------------------

    parts = []


    for part_box in parts_result.boxes:

        x1, y1, x2, y2 = map(
            int,
            part_box.xyxy[0].tolist()
        )


        class_id = int(
            part_box.cls[0]
        )


        part_area = max(
            (x2 - x1) * (y2 - y1),
            1
        )


        parts.append({

            "name":
                parts_model.names[class_id],

            "box":
                (x1, y1, x2, y2),

            "confidence":
                float(part_box.conf[0]),

            "area":
                part_area
        })


    # ----------------------------------------------
    # MATCHING
    # ----------------------------------------------

    matched_parts = {}


    for damage_index, raw_mask in enumerate(
        damage_masks
    ):

        damage_conf = float(
            damage_result
            .boxes
            .conf[damage_index]
        )


        mask = cv2.resize(
            raw_mask,
            (
                image_width,
                image_height
            ),
            interpolation=cv2.INTER_NEAREST
        ) > 0.5


        damage_area = int(
            np.sum(mask)
        )


        if damage_area == 0:
            continue


        for part in parts:

            part_name = part["name"]

            x1, y1, x2, y2 = (
                part["box"]
            )


            overlap_area = int(
                np.sum(
                    mask[
                        y1:y2,
                        x1:x2
                    ]
                )
            )


            damage_in_part_ratio = (
                overlap_area
                /
                damage_area
            )


            part_damaged_ratio = (
                overlap_area
                /
                part["area"]
            )


            if (
                damage_in_part_ratio
                >= MIN_DAMAGE_IN_PART

                and

                part_damaged_ratio
                >= MIN_PART_DAMAGED
            ):

                if part_name not in matched_parts:

                    matched_parts[part_name] = {

                        "trusted_mask":
                            np.zeros(
                                (
                                    image_height,
                                    image_width
                                ),
                                dtype=bool
                            ),

                        "candidate_mask":
                            np.zeros(
                                (
                                    image_height,
                                    image_width
                                ),
                                dtype=bool
                            ),

                        "box":
                            part["box"],

                        "part_confidence":
                            part["confidence"],

                        "damage_confidences":
                            []
                    }


                matched_parts[
                    part_name
                ]["candidate_mask"] |= mask


                if (
                    damage_conf
                    >= TRUSTED_DAMAGE_CONF
                ):

                    matched_parts[
                        part_name
                    ]["trusted_mask"] |= mask


                matched_parts[
                    part_name
                ][
                    "damage_confidences"
                ].append(
                    damage_conf
                )


    # ----------------------------------------------
    # BUILD JSON RESULTS
    # ----------------------------------------------

    results = []

    accepted_count = 0
    review_count = 0


    for part_name, data in matched_parts.items():

        x1, y1, x2, y2 = (
            data["box"]
        )


        part_area = max(
            (x2 - x1)
            *
            (y2 - y1),
            1
        )


        trusted_damage_area = int(
            np.sum(
                data["trusted_mask"][
                    y1:y2,
                    x1:x2
                ]
            )
        )


        candidate_damage_area = int(
            np.sum(
                data["candidate_mask"][
                    y1:y2,
                    x1:x2
                ]
            )
        )


        has_trusted_damage = (
            trusted_damage_area > 0
        )


        if has_trusted_damage:

            damage_percentage = (
                trusted_damage_area
                /
                part_area
            ) * 100


            severity = get_severity(
                part_name,
                damage_percentage
            )


        else:

            damage_percentage = (
                candidate_damage_area
                /
                part_area
            ) * 100


            severity = "Uncertain"


        damage_confidence = max(
            data["damage_confidences"]
        )


        status = get_status(
            data["part_confidence"],
            damage_confidence,
            has_trusted_damage
        )


        action = get_repair_action(
            part_name,
            severity,
            status
        )


        if status == "Accepted":
            accepted_count += 1

        else:
            review_count += 1


        results.append({

            "part":
                part_name,

            "severity":
                severity,

            "damage_percentage":
                round(
                    float(
                        damage_percentage
                    ),
                    2
                ),

            "damage_confidence":
                round(
                    damage_confidence,
                    2
                ),

            "part_confidence":
                round(
                    data[
                        "part_confidence"
                    ],
                    2
                ),

            "status":
                status,

            "recommended_action":
                action
        })


    return {

        "vehicle_detected":
            True,

        "vehicle_confidence":
            vehicle_confidence,

        "damage_detected":
            len(results) > 0,

        "damaged_parts":
            results,

        "summary": {

            "total_parts":
                len(results),

            "accepted":
                accepted_count,

            "review_required":
                review_count
        }
    }