#!/usr/bin/env python3
"""
Test script for GUI order integration
Simulates Customer GUI sending orders to FMS
"""

import socket
import json
import time


def send_message(sock, message):
    """Send message with 4-byte length header"""
    json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
    length_header = len(json_data).to_bytes(4, byteorder='big')
    sock.sendall(length_header + json_data)


def recv_message(sock):
    """Receive message with 4-byte length header"""
    # Receive length header
    length_header = sock.recv(4)
    if not length_header:
        return None

    message_length = int.from_bytes(length_header, byteorder='big')

    # Receive message
    data = b''
    while len(data) < message_length:
        chunk = sock.recv(message_length - len(data))
        if not chunk:
            return None
        data += chunk

    return json.loads(data.decode('utf-8'))


def test_new_order():
    """Test new order workflow"""
    print("=" * 60)
    print("Testing New Order Workflow")
    print("=" * 60)

    # Connect to FMS
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('192.168.1.3', 9000))  # FMS TCP server
    print("Connected to FMS at 192.168.1.3:9000")

    # Send new order
    order_message = {
        'command': 'new_order',
        'table_number': 1,
        'order': {
            'items': [
                {'menu_id': 'M001', 'quantity': 1}
            ]
        }
    }

    print(f"\nSending order: {json.dumps(order_message, indent=2)}")
    send_message(sock, order_message)

    # Receive response
    response = recv_message(sock)
    print(f"\nReceived response: {json.dumps(response, indent=2)}")

    if response and response.get('status') == 'success':
        order_id = response['data']['order_id']
        print(f"\nOrder accepted! Order ID: {order_id}")

        # Wait for delivery notification
        print("\nWaiting for delivery notification...")
        print("(Robot will navigate to point13 -> load food -> navigate to table1)")

        while True:
            notification = recv_message(sock)
            if notification:
                print(f"\nReceived notification: {json.dumps(notification, indent=2)}")

                if notification.get('type') == 'delivery_notification':
                    if notification['data']['status'] == 'arrived':
                        print(f"\nRobot arrived at table{notification['data']['table_number']}!")
                        print("Customer can now confirm delivery...")

                        # Simulate customer confirmation after 5 seconds
                        time.sleep(5)

                        # Send delivery confirmation
                        confirm_message = {
                            'command': 'delivery_complete',
                            'order_id': order_id,
                            'table_number': notification['data']['table_number']
                        }

                        print(f"\nSending delivery confirmation: {json.dumps(confirm_message, indent=2)}")
                        send_message(sock, confirm_message)

                        # Receive confirmation response
                        confirm_response = recv_message(sock)
                        print(f"\nConfirmation response: {json.dumps(confirm_response, indent=2)}")

                        print("\nOrder workflow completed!")
                        break
            else:
                break

    else:
        print(f"\nOrder failed: {response}")

    sock.close()
    print("\nConnection closed")


def test_delivery_complete():
    """Test delivery confirmation"""
    print("=" * 60)
    print("Testing Delivery Confirmation")
    print("=" * 60)

    # Connect to FMS
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('192.168.1.3', 9000))
    print("Connected to FMS at 192.168.1.3:9000")

    # Send delivery confirmation (assuming order already delivered)
    confirm_message = {
        'command': 'delivery_complete',
        'order_id': 'ORD-20260225123456-0001',  # Example order ID
        'table_number': 1
    }

    print(f"\nSending delivery confirmation: {json.dumps(confirm_message, indent=2)}")
    send_message(sock, confirm_message)

    # Receive response
    response = recv_message(sock)
    print(f"\nReceived response: {json.dumps(response, indent=2)}")

    sock.close()
    print("\nConnection closed")


def main():
    """Main test runner"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 test_gui_order.py [new_order|delivery_complete]")
        print("\nExamples:")
        print("  python3 test_gui_order.py new_order")
        print("  python3 test_gui_order.py delivery_complete")
        return

    test_type = sys.argv[1]

    try:
        if test_type == 'new_order':
            test_new_order()
        elif test_type == 'delivery_complete':
            test_delivery_complete()
        else:
            print(f"Unknown test type: {test_type}")
            print("Available tests: new_order, delivery_complete")

    except ConnectionRefusedError:
        print("\nERROR: Could not connect to FMS at 192.168.1.3:9000")
        print("Make sure FMS is running!")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
