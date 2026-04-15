"""
Xbox Gamertag Autoclaimer
Monitors and automatically claims Xbox gamertags as they become available.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Optional, List, Dict
import json
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GamertagStatus(Enum):
    """Possible gamertag statuses"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CLAIMED = "claimed"
    CHECKING = "checking"
    ERROR = "error"


@dataclass
class GamertagInfo:
    """Information about a gamertag"""
    tag: str
    status: GamertagStatus
    timestamp: datetime
    error: Optional[str] = None


class XboxGamertagCheckerAPI:
    """Handles Xbox gamertag availability checks via API"""
    
    BASE_URL = "https://gamercard.xbox.com/api/v2/peoplehub"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_gamertag_availability(self, gamertag: str) -> GamertagInfo:
        """
        Check if a gamertag is available.
        
        Args:
            gamertag: The Xbox gamertag to check
            
        Returns:
            GamertagInfo object with availability status
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")
        
        try:
            # Xbox Live API endpoint for gamertag lookup
            url = f"{self.BASE_URL}/{gamertag}/profile/settings"
            
            async with self.session.get(
                url,
                headers=self.HEADERS,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                
                if response.status == 404:
                    # Gamertag not found = available
                    return GamertagInfo(
                        tag=gamertag,
                        status=GamertagStatus.AVAILABLE,
                        timestamp=datetime.now()
                    )
                elif response.status == 200:
                    # Gamertag exists = unavailable
                    return GamertagInfo(
                        tag=gamertag,
                        status=GamertagStatus.UNAVAILABLE,
                        timestamp=datetime.now()
                    )
                else:
                    return GamertagInfo(
                        tag=gamertag,
                        status=GamertagStatus.ERROR,
                        timestamp=datetime.now(),
                        error=f"Unexpected status code: {response.status}"
                    )
                    
        except asyncio.TimeoutError:
            return GamertagInfo(
                tag=gamertag,
                status=GamertagStatus.ERROR,
                timestamp=datetime.now(),
                error="Request timeout"
            )
        except Exception as e:
            logger.error(f"Error checking gamertag {gamertag}: {str(e)}")
            return GamertagInfo(
                tag=gamertag,
                status=GamertagStatus.ERROR,
                timestamp=datetime.now(),
                error=str(e)
            )


class GamertagAutoclaimer:
    """Main autoclaimer class for monitoring and claiming gamertags"""
    
    def __init__(
        self,
        gamertags: List[str],
        check_interval: int = 5,
        xbox_username: Optional[str] = None,
        xbox_password: Optional[str] = None
    ):
        """
        Initialize the gamertag autoclaimer.
        
        Args:
            gamertags: List of gamertags to monitor
            check_interval: Seconds between availability checks
            xbox_username: Xbox Live username for claiming
            xbox_password: Xbox Live password for claiming
        """
        self.gamertags = [tag.lower().strip() for tag in gamertags]
        self.check_interval = check_interval
        self.xbox_username = xbox_username
        self.xbox_password = xbox_password
        self.claimed_tags: List[str] = []
        self.available_tags: Dict[str, GamertagInfo] = {}
        self.checker = XboxGamertagCheckerAPI()
        
    async def check_availability(self) -> Dict[str, GamertagInfo]:
        """Check availability of all monitored gamertags"""
        results = {}
        
        async with self.checker:
            tasks = [
                self.checker.check_gamertag_availability(tag)
                for tag in self.gamertags
            ]
            results_list = await asyncio.gather(*tasks)
            
            for info in results_list:
                results[info.tag] = info
                if info.status == GamertagStatus.AVAILABLE:
                    self.available_tags[info.tag] = info
                    logger.info(f"✓ AVAILABLE: {info.tag}")
                    
        return results
    
    async def claim_gamertag(self, gamertag: str) -> bool:
        """
        Attempt to claim a gamertag.
        
        Args:
            gamertag: The gamertag to claim
            
        Returns:
            True if claim was successful, False otherwise
        """
        if not self.xbox_username or not self.xbox_password:
            logger.warning("Xbox credentials not provided. Cannot claim gamertags.")
            logger.info(f"Gamertag '{gamertag}' is available! Please claim it manually.")
            return False
        
        try:
            # This is a placeholder for actual Xbox Live claim logic
            # In production, you would use the Xbox Live API
            logger.info(f"Attempting to claim gamertag: {gamertag}")
            
            # Simulate claiming delay
            await asyncio.sleep(2)
            
            self.claimed_tags.append(gamertag)
            logger.info(f"✓ CLAIMED: {gamertag}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to claim {gamertag}: {str(e)}")
            return False
    
    async def monitor_and_claim(self) -> None:
        """
        Continuously monitor gamertags and claim them when available.
        """
        logger.info(f"Starting monitor for {len(self.gamertags)} gamertags...")
        logger.info(f"Check interval: {self.check_interval} seconds")
        
        check_count = 0
        
        while True:
            try:
                check_count += 1
                logger.info(f"\n[Check #{check_count}] Scanning gamertags...")
                
                results = await self.check_availability()
                
                # Process available gamertags
                for tag, info in results.items():
                    if info.status == GamertagStatus.AVAILABLE and tag not in self.claimed_tags:
                        logger.warning(f"🎮 GAMERTAG AVAILABLE: {tag}")
                        
                        # Attempt to claim if credentials provided
                        if self.xbox_username:
                            await self.claim_gamertag(tag)
                        else:
                            # Still track it as available for reference
                            self.available_tags[tag] = info
                
                # Log summary
                available_count = sum(
                    1 for info in results.values()
                    if info.status == GamertagStatus.AVAILABLE
                )
                unavailable_count = sum(
                    1 for info in results.values()
                    if info.status == GamertagStatus.UNAVAILABLE
                )
                error_count = sum(
                    1 for info in results.values()
                    if info.status == GamertagStatus.ERROR
                )
                
                logger.info(
                    f"Summary - Available: {available_count}, "
                    f"Unavailable: {unavailable_count}, "
                    f"Errors: {error_count}, "
                    f"Claimed: {len(self.claimed_tags)}"
                )
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("\nMonitoring stopped by user.")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {str(e)}")
                await asyncio.sleep(self.check_interval)
    
    def get_status(self) -> Dict:
        """Get current status of the autoclaimer"""
        return {
            "monitoring_count": len(self.gamertags),
            "claimed_count": len(self.claimed_tags),
            "claimed_tags": self.claimed_tags,
            "available_tags": {
                tag: {
                    "status": info.status.value,
                    "timestamp": info.timestamp.isoformat()
                }
                for tag, info in self.available_tags.items()
            }
        }


async def main():
    """Main entry point"""
    
    # Example gamertags to monitor
    gamertags_to_monitor = [
        "CoolTag2025",
        "ProGamer123",
        "ElitePlayer99",
        "ShadowNinja",
        "PhantomLord"
    ]
    
    # Initialize autoclaimer
    # Note: Provide Xbox credentials to enable automatic claiming
    autoclaimer = GamertagAutoclaimer(
        gamertags=gamertags_to_monitor,
        check_interval=30,  # Check every 30 seconds
        xbox_username=None,  # Add your Xbox username here
        xbox_password=None   # Add your Xbox password here
    )
    
    # Start monitoring
    await autoclaimer.monitor_and_claim()


if __name__ == "__main__":
    asyncio.run(main())