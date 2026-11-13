Stop Simulating, Start Moving: See It. Detect It. Act on It. The Intel Physical AI Challenge
by Ignite Next x Intel

The Challenge
AI is great on screen, but have you ever made it move? Welcome to the Intel Physical AI Challenge at Junction. This weekend, we’re taking your models out of the cloud and giving them hands, eyes, and real-time brains

Introduction
In many factories, people still inspect parts by eye and pull out the faulty ones, because programming a robot for the job takes specialist effort. With physical AI, you show a robot a task a few dozen times and it learns a policy it can run on its own. Ignite Next and Intel bring this to Junction, so you can take a real robot arm from first demonstration to an autonomous inspection cell in one weekend. You train your models on cloud GPUs and run them on Intel Core Ultra Series 3 (Panther Lake) laptops with Intel’s open-source robotics stack, which is built to take robot AI from the lab into production.

The Challenge
Each team gets its own station with an SO-101 robot arm, a leader arm for teleoperation, a top-view camera, an inspection camera and a box of Duplo bricks, some of which you mark as defective yourself.

Start by teleoperating the arm to record demonstrations, then fine-tune a vision-language-action (VLA) policy in Physical AI Studio on cloud GPUs. In parallel, train an Anomalib model that tells good bricks from defective ones at the inspection point. Then bring both together: the arm picks each brick, shows it to the inspection camera and drops it into the “good” or “defective” bowl, fully autonomously, with your models optimized with OpenVINO and running on the laptop’s CPU, GPU and NPU. Teams that get there early can push further with faster cycles, messier brick piles, new defect types or their own twist on the task.

Insight
We want to see how close a small, low-cost setup can get to a reliable inspection cell: how few demonstrations are enough, how well the policy copes with bricks in new positions, and how fast the full loop runs on the laptop’s CPU, GPU and NPU. Ideas we would like to see include using the anomaly score to trigger a re-grasp, sharing cameras between policy and inspection, and quantizing models with OpenVINO.

Resources
Challenge terms
Please read the Challenge Terms before taking part. By participating in this challenge, you agree to these terms.

What we'll bring
You build on a complete robotics station in the Junction Hardware Lab and on Intel’s open-source Robotics AI Suite, with Intel engineers on site every day of the event.

25 stations, one per team, each with an Intel Core Ultra Series 3 (Panther Lake) laptop with 64 GB RAM
An SO-101 follower arm with wrist camera and a matching leader arm for teleoperation
Two external cameras for top view and inspection, at least one of them a RealSense D415 depth camera
Duplo bricks, sorting bowls and markers to create your own defects
Cloud GPU instances for policy training
Physical AI Studio to record demonstrations and fine-tune VLA policies
Anomalib for anomaly detection, plus OpenVINO and OpenVINO Physical AI for on-device inference
A hands-on technical session on Saturday at 12:00
Mentors
Three to five Intel robotics and edge AI engineers with expertise in Physical AI Studio, OpenVINO and Anomalib, on site every day of the event and supported by the Ignite Next team.

Main contact person
Marvin Müller, Strategic Partnerships & Value Creation Lead, Ignite Next (marvin.mueller@ignitenext.com, +49 160 1684739)
