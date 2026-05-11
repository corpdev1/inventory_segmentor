#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <random>
#include <string>

#include "spot.h"
#include "/home/hari/softwares/fast-cpp-csv-parser-master/csv.h"

/* COLORS FOR FANCY PRINT */
#define END  "\x1B[0m"
#define RED  "\x1B[31m"
#define GRN  "\x1B[32m"
#define YEL  "\x1B[33m"

#define OK "[" GRN "OK" END "]"
#define WARNING "[" YEL "WARNING" END "]"
#define FAIL "[" RED "FAIL" END "]"
/* END OF COLORS FOR FANCY PRINT */


using namespace std;

using std::chrono::high_resolution_clock;
using std::chrono::duration_cast;
using std::chrono::duration;
using std::chrono::milliseconds;

double alea()
{
	std::random_device rd;
	std::default_random_engine gen(rd());
	std::uniform_real_distribution<double> u(0,1);
	return u(gen);
}


vector<double> uniform(double a, double b, int N)
{
	vector<double> v(N);
	std::random_device rd;
	std::default_random_engine gen(rd());
	std::uniform_real_distribution<double> u(a,b);

	for (int i = 0; i < N; i++)
	{
		v[i] = u(gen);
	}

	return(v); 
}



vector<double> gaussian(double mu, double sigma, int N)
{
	vector<double> v(N);
	std::random_device rd;
	std::default_random_engine gen(rd());
	std::normal_distribution<double> d(mu,sigma);

	for (int i = 0; i < N; i++)
	{
		v[i] = d(gen);
	}

	return(v);   
}

vector<double> csv_data(std::string file_name) {
    io::CSVReader<2> in(file_name);
    in.read_header(io::ignore_extra_column, "timestamp", "n_message");

    std::vector<double> ip_data;
    std::string datetime; double value;
    while(in.read_row(datetime, value)) {
      ip_data.push_back(value);
      // std::cout<<datetime<<", "<<value<<"\n";
    }

    return ip_data;
}


void check_thresholds(Spot & S, double z_truth)
{
	double r = 0.0;
	
	r = std::abs(S.getUpperThreshold() - z_truth);
	cout << setw(20) << std::left << "Upper threshold"; 
	if ( r < 0.1)
	{
		cout << OK << endl;
	}
	else if ( r < 0.6)
	{
		cout << WARNING << " (maybe anomalies are flagged or you are not lucky, try again to verify)" << endl;
	}
	else
	{
		cout << FAIL << " (maybe anomalies are flagged or you are not lucky, try again to verify)" << endl;
	}
	
	r = std::abs(S.getLowerThreshold() + z_truth);
	cout << setw(20) << std::left << "Lower threshold";
	if ( r < 0.1)
	{
		cout << OK << endl;
	}
	else if ( r < 0.6)
	{
		cout << WARNING << " (maybe anomalies are flagged or you are not lucky, try again to verify)" << endl;
	}
	else
	{
		cout << FAIL << " (maybe anomalies are flagged or you are not lucky, try again to verify)" << endl;
	}
}

vector<double> linspace(double min, double max, int n_points)
{
	vector<double> v(n_points);
	double step = (max - min)/(n_points - 1);
	for (int i = 0; i<n_points; i++)
	{
		v[i] = min + i*step;
	}
	return v;
}

void check_up_proba(Spot & S)
{
	double q = S.config().q;
	double z_q = S.getUpperThreshold();
	vector<double> v = linspace(z_q, 5., 20);
	
	cout << setw(30) << std::left << "Upper threshold meaning"; 
	double rel_err = abs(q - S.up_probability(z_q))/q;
	if ( rel_err < 0.01 )
	{
		cout << OK << endl;
	}
	else if ( rel_err < 0.02 )
	{
		cout << WARNING << endl;
	}
	else {
		cout << FAIL << "(Relative error: " << rel_err << ", lower than 0.02 expected)" << endl;
	}

	cout << setw(30) << std::left << "Probability computation";
	double ref = S.up_probability(z_q);
	double p = 0.;
	for (auto & z: v)
	{
		p = S.up_probability(z);
		if (p > ref)
		{
			cout << FAIL << endl;
			return;
		}
		else
		{
			ref = p;
		}
		
		// cout << "P(X>" << setprecision(3) << z << ") = " << setprecision(5) << S.up_probability(z) << endl;
		// cout << "P(X>" << z << ") = " << S.up_probability(z) << endl;
	}
	cout << OK << endl;
}



void check_down_proba(Spot & S)
{
	double q = S.config().q;
	double z_q = S.getLowerThreshold();
	vector<double> v = linspace(z_q, -5., 20);
	
	cout << setw(30) << std::left << "Lower threshold meaning"; 
	double rel_err = abs(q - S.down_probability(z_q))/q;
	if ( rel_err < 0.01 )
	{
		cout << OK << endl;
	}
	else if ( rel_err < 0.02 )
	{
		cout << WARNING << endl;
	}
	else {
		cout << FAIL << "(Relative error: " << rel_err << ", lower than 0.02 expected)" << endl;
	}

	cout << setw(30) << std::left << "Probability computation";
	double ref = S.down_probability(z_q);
	double p = 0.;
	for (auto & z: v)
	{
		p = S.down_probability(z);
		//cout << "P(X<" << setprecision(3) << z << ") = " << setprecision(5) << p << endl;
		if (p > ref)
		{
			cout << FAIL << endl;
			return;
		}
		else
		{
			ref = p;
		}
	}
	cout << OK << endl;
}




void check_flagging(Spot & S)
{
	SpotStatus status = S.status();
	int al_up = status.al_up;
	int al_down = status.al_down;
	
	cout << setw(30) << std::left << "Flagging up anomalies"; 
	if ( ( al_up >= 18 ) && ( al_up <= 66 ) ) // these bounds are specific to N = 20000
	{
		cout << OK << endl;
	}
	else if ( ( al_up < 13 ) || ( al_up > 85 ) ) // these bounds are specific to N = 20000
	{
		cout << FAIL << " (this is abnormal or you are not lucky, try again to verify)" << endl;
	}
	else
	{
		cout << WARNING << " (maybe you are not lucky, try again to verify)" << endl;
	}
	
	cout << setw(30) << std::left << "Flagging down anomalies"; 
	if ( ( al_down >= 18 ) && ( al_down <= 66 ) ) // these bounds are specific to N = 20000
	{
		cout << OK << endl;
	}
	else if ( ( al_down < 13 ) || ( al_down > 85 ) ) // these bounds are specific to N = 20000
	{
		cout << FAIL << " (this is abnormal or you are not lucky, try again to verify)" << endl;
	}
	else
	{
		cout << WARNING << " (maybe you are not lucky, try again to verify)" << endl;
	}	
}


int main(int argc, const char * argv[]) {
  std::vector<std::string> ip_files = {"6040a96cdcc614001153fc55-linux60b8d8abaeb6f802698917b1-log-linux60b8d8abaeb6f802698917b1-stashed"}; 
  // {"60ddc7da72033d00111f4be1-docker-log-datadog-agent-service-master-stashed"} {"60ddc7da72033d00111f4be1-docker-log-donation-celery-develop-stashed"}

  std::ifstream list_file("../../file_list.txt");
  std::string str_line;

  /*
  while (std::getline(list_file, str_line)) {
    ip_files.push_back(str_line);
  }
  */
  /*
  std::vector<int> fit_mem_vals = {1440}; // 2880, 4320, 5760};
  std::vector<double> level_vals = {0.98, 0.99, 0.995};
  std::vector<double> q_vals = {1e-3, 5e-3, 1e-2, 5e-2};
  std::vector<int> n_init_vals = {4320, 5760, 8640};
  */
  std::vector<int> fit_mem_vals = {1440};
  std::vector<double> level_vals = {0.995};
  std::vector<double> q_vals = {0.001};
  std::vector<int> n_init_vals = {8640};

  int test_cnt = 0;

  for (auto fit_mem_val: fit_mem_vals) {
  for (auto level_val: level_vals) {
  for (auto q_val: q_vals) {
  for (auto n_init_val: n_init_vals) {
    std::string test_str = "test" + std::to_string(test_cnt++) + "_";

    std::ofstream anom_op_file(test_str + "all_anom_op.txt");
    anom_op_file<<"metric_name,up_alerts,down_alerts,total_pts,total_pts_analysed,init_win,time_ms,fit_mem_size"<<endl;

    for (auto ip_file: ip_files) {
      vector<double> all_data = csv_data("/home/hari/data/Affluences_Logfrequency_Data_2/input/" + ip_file + ".csv");	

      vector<double> data;
      data.reserve(data.size());
      vector<int> data_ind;
      data_ind.reserve(data.size());

      double sparse_thresh = 0;  // 0.05*(*std::max_element(std::begin(all_data), std::begin(all_data) + n_init_val))

      int ind_cnt = 0;
      for (auto ip_sample: all_data) {
        if (ip_sample >= sparse_thresh) {
          data.push_back(ip_sample);
          data_ind.push_back(ind_cnt);
        }
        ++ind_cnt;
      }

      int ip_size = data.size();
      int frac_ip_size = (sparse_thresh > 0) ? (int)(0.05*ip_size):0;
      int n_init_val_check = (frac_ip_size > 0) ? std::min(n_init_val, (int)(0.05*ip_size)):n_init_val;
      int fit_mem_val_check = std::min(fit_mem_val, ip_size); 

      // cout<<test_str<<"_fit_mem_val_"<<fit_mem_val_check<<"_level_val_"<<level_val<<"_q_val_"<<q_val<<"_n_init_val_"<<n_init_val_check<<endl;

      std::vector<int> op_label;
      std::vector<double> t_up_vec, z_up_vec;

      int nb_up_alarm = 0;
      int nb_down_alarm = 0;
      double time_ms = 0;

      if ((ip_size > n_init_val_check) && (n_init_val_check * (1 - level_val) > 10)) {
        op_label.reserve(ip_size);
        t_up_vec.reserve(ip_size);
        z_up_vec.reserve(ip_size);
        auto t1 = high_resolution_clock::now();
        
        Spot S(q_val,n_init_val_check,level_val,true,true,true,true,fit_mem_val_check);

        for(auto x : data) {
          auto [output, t_up, z_up] = S.custom_step(x);

          op_label.push_back(output);
          t_up_vec.push_back(t_up);
          z_up_vec.push_back(z_up);

          if (output == SPOTEVENT::ALERT_UP) {
            nb_up_alarm++;
          }
          if (output == SPOTEVENT::ALERT_DOWN) {
            nb_down_alarm++;
          }
        }

        auto t2 = high_resolution_clock::now();
        duration<double, std::milli> ms_double = t2 - t1;
        time_ms = ms_double.count();

        std::ofstream op_file(test_str + ip_file + "_anom_op.txt");
        for (auto x = op_label.begin(); x < op_label.end() - 1; ++x) {
          op_file<<*x<<" ";
        }

        if (!op_label.empty())
          op_file<<op_label.back();
 
        op_file.close();

        std::ofstream ind_file(test_str + ip_file + "_nonsparse_ind.txt");
        for (auto x = data_ind.begin(); x < data_ind.end() - 1; ++x) {
          ind_file<<*x<<" ";
        }

        if (!data_ind.empty())
          ind_file<<data_ind.back();
 
        ind_file.close();

        std::ofstream t_up_file(test_str + ip_file + "_t_up.txt");
        for (auto x = t_up_vec.begin(); x < t_up_vec.end() - 1; ++x) {
          t_up_file<<*x<<" ";
        }

        if (!t_up_vec.empty())
          t_up_file<<t_up_vec.back();
 
        t_up_file.close();

        std::ofstream z_up_file(test_str + ip_file + "_z_up.txt");
        for (auto x = z_up_vec.begin(); x < z_up_vec.end() - 1; ++x) {
          z_up_file<<*x<<" ";
        }

        if (!z_up_vec.empty())
          z_up_file<<z_up_vec.back();
 
        z_up_file.close();
      }

      // cout << "#Up Alerts: " << nb_up_alarm << " #Down Alerts: " << nb_down_alarm << endl;
      // cout << "Total number of points: "<<ip_size<<" Number of points for which anomaly is marked "<<ip_size-n_init<<" Initialization window size "<<n_init<<endl;
      anom_op_file<<ip_file<<","<<nb_up_alarm<<","<<nb_down_alarm<<","<<ip_size<<","<<ip_size-n_init_val_check<<","<<n_init_val_check<<","<<time_ms<<","<<fit_mem_val_check<<endl;
    }
    anom_op_file.close();
  }
  }
  }
  }

  return 0;
}
