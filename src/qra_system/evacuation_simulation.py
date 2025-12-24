"""
Evacuation Simulation Module
Implements agent-based evacuation modeling for quantitative risk assessment
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class Agent:
    """Represents an evacuee in the simulation"""
    id: int
    x: float
    y: float
    speed: float  # m/s
    pre_movement_time: float  # seconds
    exit_reached: bool = False
    evacuation_time: float = 0.0


@dataclass
class Exit:
    """Represents an exit in the building"""
    id: int
    x: float
    y: float
    capacity: float  # people per second


@dataclass
class Building:
    """Represents the building layout"""
    width: float  # meters
    height: float  # meters
    exits: List[Exit]
    obstacles: List[Tuple[float, float, float, float]] = None  # (x1, y1, x2, y2)


class EvacuationSimulation:
    """
    Performs evacuation simulation using a simplified agent-based model
    """
    
    def __init__(self, building: Building, num_agents: int, 
                 mean_speed: float = 1.2, std_speed: float = 0.3,
                 mean_pre_movement: float = 30.0, std_pre_movement: float = 10.0,
                 random_seed: Optional[int] = None):
        """
        Initialize evacuation simulation
        
        Args:
            building: Building configuration
            num_agents: Number of agents (occupants) to simulate
            mean_speed: Mean walking speed (m/s)
            std_speed: Standard deviation of walking speed
            mean_pre_movement: Mean pre-movement time (seconds)
            std_pre_movement: Standard deviation of pre-movement time
            random_seed: Random seed for reproducibility
        """
        self.building = building
        self.num_agents = num_agents
        self.mean_speed = mean_speed
        self.std_speed = std_speed
        self.mean_pre_movement = mean_pre_movement
        self.std_pre_movement = std_pre_movement
        
        if random_seed is not None:
            np.random.seed(random_seed)
        
        self.agents = self._initialize_agents()
        self.time_step = 0.5  # seconds
        self.max_time = 600.0  # 10 minutes maximum
    
    def _initialize_agents(self) -> List[Agent]:
        """Initialize agents with random positions and characteristics"""
        agents = []
        for i in range(self.num_agents):
            # Random position within building
            x = np.random.uniform(0, self.building.width)
            y = np.random.uniform(0, self.building.height)
            
            # Random speed (normal distribution, clipped to positive values)
            speed = max(0.3, np.random.normal(self.mean_speed, self.std_speed))
            
            # Random pre-movement time (lognormal distribution for realistic distribution)
            pre_movement = np.random.lognormal(
                np.log(self.mean_pre_movement), 
                self.std_pre_movement / self.mean_pre_movement
            )
            
            agents.append(Agent(
                id=i,
                x=x,
                y=y,
                speed=speed,
                pre_movement_time=pre_movement
            ))
        
        return agents
    
    def _find_nearest_exit(self, agent: Agent) -> Exit:
        """Find the nearest exit for an agent"""
        min_distance = float('inf')
        nearest_exit = self.building.exits[0]
        
        for exit_obj in self.building.exits:
            distance = np.sqrt((agent.x - exit_obj.x)**2 + (agent.y - exit_obj.y)**2)
            if distance < min_distance:
                min_distance = distance
                nearest_exit = exit_obj
        
        return nearest_exit
    
    def _move_agent(self, agent: Agent, current_time: float):
        """Move agent towards nearest exit"""
        if agent.exit_reached:
            return
        
        # Check if agent has started moving
        if current_time < agent.pre_movement_time:
            return
        
        # Find nearest exit
        nearest_exit = self._find_nearest_exit(agent)
        
        # Calculate direction to exit
        dx = nearest_exit.x - agent.x
        dy = nearest_exit.y - agent.y
        distance = np.sqrt(dx**2 + dy**2)
        
        # Check if reached exit (within 1 meter)
        if distance < 1.0:
            agent.exit_reached = True
            agent.evacuation_time = current_time
            return
        
        # Move towards exit
        move_distance = agent.speed * self.time_step
        if move_distance > distance:
            move_distance = distance
        
        agent.x += (dx / distance) * move_distance
        agent.y += (dy / distance) * move_distance
    
    def run_simulation(self) -> Dict[str, Any]:
        """
        Run the evacuation simulation
        
        Returns:
            Dictionary containing simulation results
        """
        current_time = 0.0
        
        while current_time < self.max_time:
            # Move all agents
            for agent in self.agents:
                self._move_agent(agent, current_time)
            
            # Check if all agents evacuated
            if all(agent.exit_reached for agent in self.agents):
                break
            
            current_time += self.time_step
        
        # Collect results
        evacuation_times = [agent.evacuation_time for agent in self.agents 
                           if agent.exit_reached]
        
        # Handle agents who didn't evacuate
        for agent in self.agents:
            if not agent.exit_reached:
                agent.evacuation_time = self.max_time
                evacuation_times.append(self.max_time)
        
        results = {
            'evacuation_times': np.array(evacuation_times),
            'mean_evacuation_time': np.mean(evacuation_times),
            'max_evacuation_time': np.max(evacuation_times),
            'min_evacuation_time': np.min(evacuation_times),
            'std_evacuation_time': np.std(evacuation_times),
            'num_evacuated': sum(1 for a in self.agents if a.exit_reached),
            'num_total': self.num_agents,
            'agents': self.agents
        }
        
        return results
    
    def run_multiple_simulations(self, num_simulations: int) -> List[Dict[str, Any]]:
        """
        Run multiple simulations with different random seeds
        
        Args:
            num_simulations: Number of simulations to run
            
        Returns:
            List of simulation results
        """
        all_results = []
        
        for i in range(num_simulations):
            # Reinitialize agents for each simulation
            self.agents = self._initialize_agents()
            results = self.run_simulation()
            all_results.append(results)
        
        return all_results


def create_simple_building(width: float = 50.0, height: float = 30.0, 
                          num_exits: int = 2) -> Building:
    """
    Create a simple rectangular building with exits
    
    Args:
        width: Building width in meters
        height: Building height in meters
        num_exits: Number of exits
        
    Returns:
        Building object
    """
    exits = []
    
    if num_exits == 1:
        exits.append(Exit(id=0, x=width/2, y=0, capacity=2.0))
    elif num_exits == 2:
        exits.append(Exit(id=0, x=0, y=height/2, capacity=2.0))
        exits.append(Exit(id=1, x=width, y=height/2, capacity=2.0))
    elif num_exits >= 3:
        exits.append(Exit(id=0, x=0, y=height/2, capacity=2.0))
        exits.append(Exit(id=1, x=width, y=height/2, capacity=2.0))
        exits.append(Exit(id=2, x=width/2, y=0, capacity=2.0))
    
    return Building(width=width, height=height, exits=exits)
