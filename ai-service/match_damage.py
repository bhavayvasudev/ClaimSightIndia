from ultralytics import YOLO
import numpy as np
import cv2
import os


# ==================================================
# CONFIG
# ==================================================

TEST_FOLDER = "test-images"

PARTS_CONF = 0.10

# Low threshold to discover subtle damage
DAMAGE_CONF = 0.08

# Damage confidence required to affect severity
TRUSTED_DAMAGE_CONF = 0.18

# Spatial matching thresholds
MIN_DAMAGE_IN_PART = 0.10
MIN_PART_DAMAGED = 0.02


# ==================================================
# LOAD MODELS
# ==================================================

parts_model = YOLO(
    "models/car_parts_best.pt"
)

damage_model = YOLO(
    "models/damage_seg_50_best.pt"
)


# ==================================================
# SEVERITY
# ==================================================

def get_severity(part_name, damage_percentage):

    name = part_name.lower()

    # Lights
    if (
        "headlight" in name
        or "rear light" in name
        or "tail light" in name
    ):

        if damage_percentage < 10:
            return "Minor"

        elif damage_percentage < 25:
            return "Moderate"

        else:
            return "Severe"


    # Body panels
    elif any(
        word in name
        for word in [
            "hood",
            "door",
            "fender",
            "bonnet",
            "boot"
        ]
    ):

        if damage_percentage < 12:
            return "Minor"

        elif damage_percentage < 35:
            return "Moderate"

        else:
            return "Severe"


    # Bumpers
    elif "bumper" in name:

        if damage_percentage < 15:
            return "Minor"

        elif damage_percentage < 40:
            return "Moderate"

        else:
            return "Severe"


    # Fallback
    else:

        if damage_percentage < 10:
            return "Minor"

        elif damage_percentage < 30:
            return "Moderate"

        else:
            return "Severe"


# ==================================================
# STATUS
# ==================================================

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


# ==================================================
# REPAIR / REPLACE DECISION
# ==================================================

def get_repair_action(
    part_name,
    severity,
    status
):

    name = part_name.lower()


    # Weak or uncertain detections
    if (
        status == "Review Required"
        or severity == "Uncertain"
    ):

        return "Manual Inspection"


    # Lights
    if any(
        x in name
        for x in [
            "headlight",
            "rear light",
            "tail light"
        ]
    ):

        if severity == "Minor":
            return "Repair"

        return "Replace"


    # Bumpers
    if "bumper" in name:

        if severity in [
            "Minor",
            "Moderate"
        ]:

            return "Repair"

        return "Replace"


    # Body panels
    if any(
        x in name
        for x in [
            "hood",
            "bonnet",
            "door",
            "fender",
            "boot"
        ]
    ):

        if severity == "Minor":
            return "Repair"

        elif severity == "Moderate":
            return "Repair + Repaint"

        else:
            return "Replace / Major Repair"


    # Default
    if severity == "Minor":
        return "Repair"

    elif severity == "Moderate":
        return "Repair + Repaint"

    return "Replace / Major Repair"


# ==================================================
# COST ESTIMATION
# ==================================================

def get_cost_estimate(
    part_name,
    action
):

    name = part_name.lower()


    # Manual inspection
    if action == "Manual Inspection":
        return None, None


    # Headlights
    if "headlight" in name:

        if action == "Repair":
            return 1500, 4000

        return 5000, 25000


    # Rear lights
    if (
        "rear light" in name
        or "tail light" in name
    ):

        if action == "Repair":
            return 1000, 3000

        return 3000, 15000


    # Bumpers
    if "bumper" in name:

        if action == "Repair":
            return 2500, 7000

        return 7000, 20000


    # Hood / bonnet
    if (
        "hood" in name
        or "bonnet" in name
    ):

        if action == "Repair":
            return 3000, 7000

        elif action == "Repair + Repaint":
            return 6000, 12000

        return 12000, 30000


    # Doors
    if "door" in name:

        if action == "Repair":
            return 2500, 6000

        elif action == "Repair + Repaint":
            return 5000, 10000

        return 10000, 30000


    # Fenders
    if "fender" in name:

        if action == "Repair":
            return 2000, 5000

        elif action == "Repair + Repaint":
            return 4000, 8000

        return 7000, 18000


    # Boot
    if "boot" in name:

        if action == "Repair":
            return 3000, 7000

        elif action == "Repair + Repaint":
            return 6000, 12000

        return 12000, 30000


    # Generic fallback
    if action == "Repair":
        return 2000, 6000

    elif action == "Repair + Repaint":
        return 5000, 12000

    return 10000, 30000


# ==================================================
# FIND TEST IMAGES
# ==================================================

image_files = [

    file

    for file in os.listdir(TEST_FOLDER)

    if file.lower().endswith(
        (
            ".jpg",
            ".jpeg",
            ".png"
        )
    )
]


print(
    f"\nFound {len(image_files)} test images."
)


# ==================================================
# PROCESS IMAGES
# ==================================================

for image_file in image_files:

    image_path = os.path.join(
        TEST_FOLDER,
        image_file
    )


    print("\n" + "=" * 60)

    print(
        f"IMAGE: {image_file}"
    )

    print("=" * 60)


    # ----------------------------------------------
    # RUN MODELS
    # ----------------------------------------------

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


    # ----------------------------------------------
    # NO DAMAGE
    # ----------------------------------------------

    if damage_result.masks is None:

        print("No damage detected.")

        continue


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


    # ==================================================
    # STORE PART DETECTIONS
    # ==================================================

    parts = []


    for part_box in parts_result.boxes:

        x1, y1, x2, y2 = map(

            int,

            part_box
            .xyxy[0]
            .tolist()

        )


        class_id = int(
            part_box.cls[0]
        )


        part_name = (
            parts_model.names[class_id]
        )


        part_confidence = float(
            part_box.conf[0]
        )


        part_area = max(

            (x2 - x1)
            *
            (y2 - y1),

            1

        )


        parts.append({

            "name":
                part_name,

            "box":
                (x1, y1, x2, y2),

            "confidence":
                part_confidence,

            "area":
                part_area
        })


    # ==================================================
    # MATCH DAMAGE TO PARTS
    # ==================================================

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

            interpolation=
                cv2.INTER_NEAREST

        ) > 0.5


        damage_area = int(
            np.sum(mask)
        )


        if damage_area == 0:
            continue


        # ------------------------------------------
        # CHECK MASK AGAINST EVERY PART
        # ------------------------------------------

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


            # Percentage of damage mask
            # located inside this part
            damage_in_part_ratio = (

                overlap_area
                /
                damage_area

            )


            # Percentage of part covered
            # by this damage mask
            part_damaged_ratio = (

                overlap_area
                /
                part["area"]

            )


            # --------------------------------------
            # TWO-WAY SPATIAL CHECK
            # --------------------------------------

            if (

                damage_in_part_ratio
                >= MIN_DAMAGE_IN_PART

                and

                part_damaged_ratio
                >= MIN_PART_DAMAGED

            ):


                if part_name not in matched_parts:

                    matched_parts[
                        part_name
                    ] = {


                        # Trusted masks affect
                        # severity calculation
                        "trusted_mask":
                            np.zeros(
                                (
                                    image_height,
                                    image_width
                                ),
                                dtype=bool
                            ),


                        # Candidate masks include
                        # weak detections too
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


                # ----------------------------------
                # STORE CANDIDATE MASK
                # ----------------------------------

                matched_parts[
                    part_name
                ][
                    "candidate_mask"
                ] |= mask


                # ----------------------------------
                # STORE TRUSTED MASK
                # ----------------------------------

                if (
                    damage_conf
                    >= TRUSTED_DAMAGE_CONF
                ):

                    matched_parts[
                        part_name
                    ][
                        "trusted_mask"
                    ] |= mask


                matched_parts[
                    part_name
                ][
                    "damage_confidences"
                ].append(
                    damage_conf
                )


    # ==================================================
    # NO MATCHED PARTS
    # ==================================================

    if not matched_parts:

        print(
            "Damage detected, but no parts matched."
        )

        continue


    # ==================================================
    # FINAL REPORT
    # ==================================================

    for part_name, data in (
        matched_parts.items()
    ):


        x1, y1, x2, y2 = (
            data["box"]
        )


        part_area = max(

            (x2 - x1)
            *
            (y2 - y1),

            1

        )


        # ------------------------------------------
        # TRUSTED DAMAGE AREA
        # ------------------------------------------

        trusted_damage_area = int(

            np.sum(

                data[
                    "trusted_mask"
                ][

                    y1:y2,

                    x1:x2

                ]

            )

        )


        # ------------------------------------------
        # CANDIDATE DAMAGE AREA
        # ------------------------------------------

        candidate_damage_area = int(

            np.sum(

                data[
                    "candidate_mask"
                ][

                    y1:y2,

                    x1:x2

                ]

            )

        )


        has_trusted_damage = (
            trusted_damage_area > 0
        )


        # ------------------------------------------
        # SEVERITY
        # ------------------------------------------

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


        max_damage_confidence = max(

            data[
                "damage_confidences"
            ]

        )


        # ------------------------------------------
        # STATUS
        # ------------------------------------------

        status = get_status(

            data[
                "part_confidence"
            ],

            max_damage_confidence,

            has_trusted_damage

        )


        # ------------------------------------------
        # REPAIR ACTION
        # ------------------------------------------

        action = get_repair_action(

            part_name,

            severity,

            status

        )


        # ------------------------------------------
        # COST ESTIMATE
        # ------------------------------------------

        cost_min, cost_max = (
            get_cost_estimate(

                part_name,

                action

            )
        )


        # ------------------------------------------
        # FINAL RESULT
        # ------------------------------------------

        result = {

            "image":
                image_file,

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
                    max_damage_confidence,
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
                action,

            "estimated_cost":
                (
                    f"₹{cost_min:,} - ₹{cost_max:,}"

                    if cost_min is not None

                    else "Inspection Required"
                )
        }


        print(result)


# ==================================================
# COMPLETE
# ==================================================

print("\n" + "=" * 60)

print("ANALYSIS COMPLETE")

print(
    f"Processed images: {len(image_files)}"
)

print("=" * 60)