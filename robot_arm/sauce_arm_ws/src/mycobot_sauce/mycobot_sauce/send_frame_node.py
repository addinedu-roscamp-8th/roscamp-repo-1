
import json
import socket
import struct
import time
from typing import Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

from mycobot_sauce_msgs.srv import SendFrame


MAGIC = b"Q1"


def now_ms() -> int:
    return int(time.time() * 1000)


class SendFrameNode(Node):
    def __init__(self):
        super().__init__("send_frame_node")

        # defaults (used when request.server_ip/port empty or zero)
        self.declare_parameter("default_server_ip", "127.0.0.1")
        self.declare_parameter("default_server_port", 9000)

        # jpeg / udp tuning
        self.declare_parameter("jpeg_quality", 80)
        self.declare_parameter("udp_chunk_bytes", 60000)
        self.declare_parameter("udp_retry", 1)

        # internal
        self._bridge = CvBridge()
        self._latest_img: Optional[Image] = None
        self._img_stamp_ms: int = 0

        self._srv = self.create_service(SendFrame, "send_frame", self.handle_send_frame)

        self.get_logger().info("Ready: /send_frame (srv)")

    # -----------------------------
    # image capture / encode
    # -----------------------------
    def _capture_one_frame(self, topic: str, timeout_sec: float) -> Optional[Image]:
        self._latest_img = None
        self._img_stamp_ms = 0

        def cb(msg: Image):
            if self._latest_img is None:
                self._latest_img = msg
                self._img_stamp_ms = now_ms()

        sub = self.create_subscription(Image, topic, cb, qos_profile_sensor_data)

        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self._latest_img is not None:
                self.destroy_subscription(sub)
                return self._latest_img

        self.destroy_subscription(sub)
        return None

    def _encode_jpeg(self, img_msg: Image) -> bytes:
        cv_img = self._bridge.imgmsg_to_cv2(img_msg, desired_encoding="bgr8")
        q = int(self.get_parameter("jpeg_quality").value)
        ok, buf = cv2.imencode(".jpg", cv_img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        if not ok:
            raise RuntimeError("jpeg_encode_failed")
        return buf.tobytes()

    # -----------------------------
    # udp protocol
    # -----------------------------
    def _udp_send_chunks_and_wait(
        self,
        job_id: str,
        jpeg: bytes,
        server_ip: str,
        server_port: int,
        timeout_sec: float,
    ) -> Tuple[bool, float, str]:
        chunk_bytes = int(self.get_parameter("udp_chunk_bytes").value)
        retry = int(self.get_parameter("udp_retry").value)

        chunks = [jpeg[i : i + chunk_bytes] for i in range(0, len(jpeg), chunk_bytes)]
        total = len(chunks)
        if total <= 0:
            raise RuntimeError("empty_jpeg")

        job_b = job_id.encode("utf-8")
        if len(job_b) > 200:
            raise RuntimeError("job_id_too_long")

        addr = (server_ip, int(server_port))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(float(timeout_sec))

        last_err = "no_response"
        for _ in range(retry + 1):
            # send all chunks
            for seq, payload in enumerate(chunks):
                header = bytearray()
                header += MAGIC
                header += struct.pack("!B", len(job_b))
                header += job_b
                header += struct.pack("!HHH", total, seq, len(payload))
                sock.sendto(bytes(header) + payload, addr)

            # wait response (one json)
            try:
                data, _ = sock.recvfrom(4096)
                resp = json.loads(data.decode("utf-8", errors="replace"))
                ok = bool(resp.get("ok", False))
                score = float(resp.get("score", 0.0))
                msg = str(resp.get("message", "ok" if ok else "defect"))
                sock.close()
                return ok, score, msg
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"

        sock.close()
        raise RuntimeError(f"udp_failed: {last_err}")

    # -----------------------------
    # srv callback
    # -----------------------------
    def handle_send_frame(self, req: SendFrame.Request, res: SendFrame.Response) -> SendFrame.Response:
        try:
            if not req.image_topic:
                res.success = False
                res.ok = False
                res.score = 0.0
                res.message = "image_topic_empty"
                return res

            server_ip = req.server_ip or str(self.get_parameter("default_server_ip").value)
            server_port = int(req.server_port) if int(req.server_port) > 0 else int(self.get_parameter("default_server_port").value)
            timeout_sec = float(req.timeout_sec) if float(req.timeout_sec) > 0 else 2.0

            img = self._capture_one_frame(req.image_topic, timeout_sec=timeout_sec)
            if img is None:
                res.success = False
                res.ok = False
                res.score = 0.0
                res.message = "capture_timeout"
                return res

            jpeg = self._encode_jpeg(img)

            ok, score, msg = self._udp_send_chunks_and_wait(
                job_id=req.job_id or "job",
                jpeg=jpeg,
                server_ip=server_ip,
                server_port=server_port,
                timeout_sec=timeout_sec,
            )

            res.success = True
            res.ok = bool(ok)
            res.score = float(score)
            res.message = msg
            return res

        except Exception as e:
            res.success = False
            res.ok = False
            res.score = 0.0
            res.message = f"exception: {e}"
            return res


def main():
    rclpy.init()
    node = SendFrameNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()