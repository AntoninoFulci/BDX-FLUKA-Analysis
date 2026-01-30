import datetime
import math
import ROOT
from typing import List, Tuple

class SimulationSummary:
    """Class to handle processing and analysis of simulation summary data"""
    
    def __init__(self, summary_dataframe):
        """Initialize with a RDataFrame containing summary data"""
        self.RSummary = summary_dataframe

    @classmethod
    def read_eot_from_file(cls, summary_file_path: str) -> float:
        """Read EOT value from an existing simulation summary file
        
        Args:
            summary_file_path: Path to the simulation summary ROOT file
            
        Returns:
            float: Total number of events (EOT)
        """
        try:
            summary_file = ROOT.TFile(summary_file_path, "READ")
            if not summary_file or summary_file.IsZombie():
                raise FileNotFoundError(f"Cannot open simulation summary file: {summary_file_path}")
            
            tree = summary_file.Get("SimSummary")
            if not tree:
                raise ValueError(f"SimSummary tree not found in {summary_file_path}")
            
            # Read the EOT value from the tree
            tree.GetEntry(0)  # Get first (and only) entry
            eot_value = tree.EOT
            
            summary_file.Close()
            print(f"Read EOT from existing summary file: {eot_value}")
            return eot_value
            
        except Exception as e:
            raise RuntimeError(f"Error reading EOT from summary file {summary_file_path}: {e}")

    def process_summary(self, output_file: ROOT.TFile) -> float:
        """Process and save summary information
        
        Args:
            output_file: ROOT file to save summary data to
            
        Returns:
            float: Total number of events (EOT)
        """
        TotEvents = self.RSummary.Sum("TotEvents")
        AvgTime = self.RSummary.Mean("AvgTime")

        MeanAvgTime = AvgTime.GetValue()
        EOT = TotEvents.GetValue()

        min_start_time = self.RSummary.Min("StartTime").GetValue()
        max_start_time = self.RSummary.Max("StartTime").GetValue()

        print(f"Total number of primaries simulated: {TotEvents.GetValue()}")
        print(f"Mean AvgTime per primary: {MeanAvgTime:.3e} s")

        # Create and fill summary tree
        tree = ROOT.TTree("SimSummary", "Summary of simulation")
        
        from array import array
        bMeanAvgTime = array('d', [0])
        bEOT = array('d', [0])
        bMinStart = array('d', [0])
        bMaxEnd = array('d', [0])
        bTotalDuration = array('d', [0])
        bAverageParallelJobs = array('d', [0])

        tree.Branch("MeanAvgTime", bMeanAvgTime, "MeanAvgTime/D")
        tree.Branch("EOT", bEOT, "EOT/D")
        tree.Branch("MinStart", bMinStart, "MinStart/D")
        tree.Branch("MaxEnd", bMaxEnd, "MaxEnd/D")
        tree.Branch("TotalDuration", bTotalDuration, "TotalDuration/D")
        tree.Branch("AverageParallelJobs", bAverageParallelJobs, "AverageParallelJobs/D")

        # Process timing information
        start_times = self.RSummary.AsNumpy(["StartTime"])["StartTime"]
        runtimes = self.RSummary.AsNumpy(["TotTime"])["TotTime"]
        end_times = start_times + runtimes
        
        # Convert to datetime
        start_times = [datetime.datetime.fromtimestamp(t) for t in start_times]
        end_times = [datetime.datetime.fromtimestamp(t) for t in end_times]
        
        min_start = min(start_times)
        max_end = max(end_times)
        total_duration = (max_end - min_start).total_seconds()
        
        # Calculate average parallel jobs
        average_parallel_jobs, std_error = self._calculate_parallel_jobs(start_times, end_times, total_duration)
        
        # Fill tree values
        bMeanAvgTime[0] = MeanAvgTime
        bEOT[0] = EOT
        bMinStart[0] = min_start.timestamp()
        bMaxEnd[0] = max_end.timestamp()
        bTotalDuration[0] = total_duration
        bAverageParallelJobs[0] = average_parallel_jobs

        tree.Fill()
        tree.Write()
        
        return EOT

    def _calculate_parallel_jobs(self, start_times: List[datetime.datetime], 
                               end_times: List[datetime.datetime], 
                               total_duration: float) -> Tuple[float, float]:
        """Calculate average number of parallel jobs running
        
        Args:
            start_times: List of job start times
            end_times: List of job end times
            total_duration: Total duration of all jobs in seconds
            
        Returns:
            Tuple containing:
            - float: Average number of parallel jobs
            - float: Standard error of the average
        """
        time_events = []
        for start, end in zip(start_times, end_times):
            time_events.append((start, 1))
            time_events.append((end, -1))
        
        time_events.sort()
        
        active_jobs = 0
        time_intervals = []
        prev_time = min(start_times)
        
        for event_time, delta in time_events:
            delta_time = (event_time - prev_time).total_seconds()
            if delta_time > 0:
                time_intervals.append((delta_time, active_jobs))
            active_jobs += delta
            prev_time = event_time
            
        weighted_sum = sum(dt * jobs for dt, jobs in time_intervals)
        average_parallel_jobs = weighted_sum / total_duration if total_duration > 0 else 0
        
        variance = sum(dt * (jobs - average_parallel_jobs)**2 for dt, jobs in time_intervals) / total_duration
        std_dev = math.sqrt(variance)
        std_error = std_dev / math.sqrt(len(time_intervals))
        
        return average_parallel_jobs, std_error
