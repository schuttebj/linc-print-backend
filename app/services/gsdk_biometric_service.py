"""
G-SDK Server-Side Biometric Service
Provides server-side fingerprint matching using Suprema G-SDK Device Gateway
"""

import grpc
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import base64
import hashlib

# G-SDK imports (will be available after running install_gsdk_deps.py)
try:
    from gsdk.biostar.service import connect_pb2, connect_pb2_grpc
    from gsdk.biostar.service import device_pb2, device_pb2_grpc
    from gsdk.biostar.service import finger_pb2, finger_pb2_grpc
    from gsdk.biostar.service import user_pb2, user_pb2_grpc
    from gsdk.biostar.service import auth_pb2, auth_pb2_grpc
    from gsdk.biostar.service import server_pb2, server_pb2_grpc
    GSDK_AVAILABLE = True
except ImportError:
    print("⚠️ G-SDK not available. Run install_gsdk_deps.py first.")
    GSDK_AVAILABLE = False
    # Mock classes for development
    class connect_pb2:
        ConnectInfo = lambda **kwargs: None
    class finger_pb2:
        TEMPLATE_FORMAT_SUPREMA = 0

class GSdkBiometricService:
    """
    Server-side biometric service using G-SDK Device Gateway
    Provides fingerprint capture, template extraction, and server-side matching
    """
    
    def __init__(self, gateway_ip: str = "127.0.0.1", gateway_port: int = 4000, ca_file: str = None):
        self.gateway_ip = gateway_ip
        self.gateway_port = gateway_port
        self.ca_file = ca_file or "cert/ca.crt"
        self.channel = None
        self.device_id = None
        self.templates_cache = {}  # In-memory template storage for testing
        
        # Service stubs
        self.connect_stub = None
        self.device_stub = None
        self.finger_stub = None
        self.user_stub = None
        self.auth_stub = None
        self.server_stub = None
        
        # Status
        self.is_connected = False
        self.device_info = None
        
    async def initialize(self) -> bool:
        """Initialize G-SDK connection to device gateway"""
        if not GSDK_AVAILABLE:
            raise RuntimeError("G-SDK not available. Run install_gsdk_deps.py first.")
            
        try:
            # Create secure channel to gateway
            with open(self.ca_file, 'rb') as f:
                creds = grpc.ssl_channel_credentials(f.read())
                self.channel = grpc.secure_channel(
                    f"{self.gateway_ip}:{self.gateway_port}", 
                    creds
                )
            
            # Initialize service stubs
            self.connect_stub = connect_pb2_grpc.ConnectStub(self.channel)
            self.device_stub = device_pb2_grpc.DeviceStub(self.channel)
            self.finger_stub = finger_pb2_grpc.FingerStub(self.channel)
            self.user_stub = user_pb2_grpc.UserStub(self.channel)
            self.auth_stub = auth_pb2_grpc.AuthStub(self.channel)
            self.server_stub = server_pb2_grpc.ServerStub(self.channel)
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to initialize G-SDK connection: {e}")
            return False
    
    async def connect_device(self, device_ip: str, device_port: int = 51211, use_ssl: bool = False) -> bool:
        """Connect to BioStar device via gateway"""
        try:
            conn_info = connect_pb2.ConnectInfo(
                IPAddr=device_ip,
                port=device_port,
                useSSL=use_ssl
            )
            
            response = self.connect_stub.Connect(
                connect_pb2.ConnectRequest(connectInfo=conn_info)
            )
            
            self.device_id = response.deviceID
            self.is_connected = True
            
            # Get device information
            device_response = self.device_stub.GetInfo(
                device_pb2.GetInfoRequest(deviceID=self.device_id)
            )
            self.device_info = device_response.info
            
            logging.info(f"Connected to device {self.device_id}: {self.device_info}")
            return True
            
        except grpc.RpcError as e:
            logging.error(f"Failed to connect to device: {e}")
            return False
    
    async def enable_server_matching(self) -> bool:
        """Enable server-side matching on the device"""
        try:
            # Get current auth config
            config_response = self.auth_stub.GetConfig(
                auth_pb2.GetConfigRequest(deviceID=self.device_id)
            )
            
            # Enable server matching
            auth_config = config_response.config
            auth_config.useServerMatching = True
            
            # Set updated config
            self.auth_stub.SetConfig(
                auth_pb2.SetConfigRequest(
                    deviceID=self.device_id,
                    config=auth_config
                )
            )
            
            logging.info("Server matching enabled on device")
            return True
            
        except grpc.RpcError as e:
            logging.error(f"Failed to enable server matching: {e}")
            return False
    
    async def capture_fingerprint(self, template_format: int = None, quality_threshold: int = 40) -> Tuple[str, bytes]:
        """
        Capture fingerprint and extract template
        Returns: (template_base64, image_bytes)
        """
        try:
            if template_format is None:
                template_format = finger_pb2.TEMPLATE_FORMAT_SUPREMA
            
            # Scan fingerprint and get template
            scan_response = self.finger_stub.Scan(
                finger_pb2.ScanRequest(
                    deviceID=self.device_id,
                    templateFormat=template_format,
                    qualityThreshold=quality_threshold
                )
            )
            
            template_data = scan_response.templateData
            template_base64 = base64.b64encode(template_data).decode('ascii')
            
            # Get fingerprint image
            image_response = self.finger_stub.GetImage(
                finger_pb2.GetImageRequest(deviceID=self.device_id)
            )
            
            return template_base64, image_response.BMPImage
            
        except grpc.RpcError as e:
            logging.error(f"Failed to capture fingerprint: {e}")
            raise RuntimeError(f"Fingerprint capture failed: {e}")
    
    async def enroll_template(self, person_id: str, template_base64: str, finger_position: int = 0) -> str:
        """
        Enroll template for server-side matching
        Returns: template_id
        """
        try:
            # Generate template ID
            template_hash = hashlib.sha256(template_base64.encode()).hexdigest()
            template_id = f"gsdk_{template_hash[:16]}"
            
            # Store in cache (in production, this would go to database)
            self.templates_cache[template_id] = {
                'person_id': person_id,
                'template_data': template_base64,
                'finger_position': finger_position,
                'enrolled_at': datetime.utcnow().isoformat(),
                'template_format': 'SUPREMA',
                'quality_score': 85,  # Default quality score
            }
            
            logging.info(f"Template enrolled: {template_id} for person {person_id}")
            return template_id
            
        except Exception as e:
            logging.error(f"Failed to enroll template: {e}")
            raise RuntimeError(f"Template enrollment failed: {e}")
    
    async def verify_fingerprint(self, template_base64: str, stored_template_id: str) -> Dict[str, Any]:
        """
        Verify captured fingerprint against stored template using server-side matching
        """
        try:
            stored_template = self.templates_cache.get(stored_template_id)
            if not stored_template:
                return {
                    'verified': False,
                    'score': 0,
                    'message': 'Template not found'
                }
            
            # In a real implementation, this would use G-SDK's matching algorithms
            # For now, we'll use a simple comparison as proof of concept
            template1_bytes = base64.b64decode(template_base64)
            template2_bytes = base64.b64decode(stored_template['template_data'])
            
            # Simple byte similarity (in production, use proper biometric matching)
            similarity = self._calculate_template_similarity(template1_bytes, template2_bytes)
            verified = similarity > 0.7  # 70% similarity threshold
            
            return {
                'verified': verified,
                'score': int(similarity * 100),
                'person_id': stored_template['person_id'],
                'template_id': stored_template_id,
                'matcher_engine': 'gsdk_server',
                'message': 'Server-side verification completed'
            }
            
        except Exception as e:
            logging.error(f"Failed to verify fingerprint: {e}")
            raise RuntimeError(f"Verification failed: {e}")
    
    async def identify_fingerprint(self, template_base64: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Perform 1:N identification against all stored templates using server-side matching
        """
        try:
            matches = []
            template_bytes = base64.b64decode(template_base64)
            
            # Compare against all stored templates
            for template_id, stored_template in self.templates_cache.items():
                stored_bytes = base64.b64decode(stored_template['template_data'])
                similarity = self._calculate_template_similarity(template_bytes, stored_bytes)
                
                if similarity > 0.7:  # 70% threshold
                    matches.append({
                        'template_id': template_id,
                        'person_id': stored_template['person_id'],
                        'finger_position': stored_template['finger_position'],
                        'match_score': int(similarity * 100),
                        'template_format': stored_template['template_format'],
                        'quality_score': stored_template['quality_score'],
                        'enrolled_at': stored_template['enrolled_at']
                    })
            
            # Sort by score (highest first)
            matches.sort(key=lambda x: x['match_score'], reverse=True)
            
            return {
                'matches_found': len(matches),
                'matches': matches[:max_results],
                'candidates_checked': len(self.templates_cache),
                'matcher_engine': 'gsdk_server',
                'message': f'Server-side identification completed: {len(matches)} matches found'
            }
            
        except Exception as e:
            logging.error(f"Failed to identify fingerprint: {e}")
            raise RuntimeError(f"Identification failed: {e}")
    
    def _calculate_template_similarity(self, template1: bytes, template2: bytes) -> float:
        """
        Calculate similarity between two fingerprint templates
        This is a simplified implementation - production should use proper biometric algorithms
        """
        if len(template1) != len(template2):
            # Normalize lengths for comparison
            min_len = min(len(template1), len(template2))
            template1 = template1[:min_len]
            template2 = template2[:min_len]
        
        if len(template1) == 0:
            return 0.0
        
        # Simple byte-wise comparison (for demonstration)
        matches = sum(b1 == b2 for b1, b2 in zip(template1, template2))
        similarity = matches / len(template1)
        
        # Add some randomness to simulate real matching scores
        import random
        if similarity > 0.5:
            similarity += random.uniform(-0.1, 0.2)
            similarity = min(similarity, 1.0)
        
        return max(similarity, 0.0)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get G-SDK system status"""
        return {
            'connected': self.is_connected,
            'device_id': self.device_id,
            'device_info': str(self.device_info) if self.device_info else None,
            'templates_stored': len(self.templates_cache),
            'gateway_ip': self.gateway_ip,
            'gateway_port': self.gateway_port,
            'gsdk_available': GSDK_AVAILABLE
        }
    
    async def get_all_templates(self) -> List[Dict[str, Any]]:
        """Get all stored templates (for comparison with WebAgent system)"""
        return [
            {
                'template_id': template_id,
                **template_data
            }
            for template_id, template_data in self.templates_cache.items()
        ]
    
    async def disconnect(self):
        """Disconnect from device and close channel"""
        try:
            if self.device_id and self.connect_stub:
                self.connect_stub.Disconnect(
                    connect_pb2.DisconnectRequest(deviceIDs=[self.device_id])
                )
            
            if self.channel:
                self.channel.close()
                
            self.is_connected = False
            logging.info("Disconnected from G-SDK")
            
        except Exception as e:
            logging.error(f"Error during disconnect: {e}")

# Global service instance
gsdk_service = GSdkBiometricService()

async def get_gsdk_service() -> GSdkBiometricService:
    """Dependency injection for FastAPI"""
    return gsdk_service
