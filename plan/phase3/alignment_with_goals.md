- Targeted Footfall Tracking: Phase 3 introduces Region of Interest (ROI) configuration for each camera, allowing the system to focus detection on doorway areas. This aligns with the goal of accurate entry/exit footfall counting by reducing false detections outside the door region.

- Entry/Exit Differentiation: By letting users label which direction (left-to-right vs. right-to-left) corresponds to an entry vs. an exit, the system can now distinguish footfall event types. This directly supports the goal of tracking not just total traffic but also inbound vs. outbound counts, making the analytics more meaningful.

- User Configurability & UX: Providing a simple visual setup for ROIs in the dashboard improves usability. Non-technical users can configure the camera’s detection zone and direction mapping without modifying code. This keeps the solution user-friendly, which was a key project goal.

- Persistence & Reliability: Storing the ROI and direction settings per camera and auto-applying them on startup ensures the system remembers configurations. This persistence aligns with creating a reliable, always-on system that doesn’t require reconfiguration on each run.

- Modular Multi-Camera Support: The ROI/direction mechanism is designed per camera, laying groundwork for multi-camera setups. While Phase 3 still uses a single camera, the implementation is extensible – each camera can have its own ROI and entry/exit direction setting. This forwards the project goal of scaling to multiple cameras in future phases.