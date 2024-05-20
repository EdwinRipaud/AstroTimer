#include <iostream>
#include <unistd.h>
#include <pigpio.h>

int OFFSET_t = 300000;
int PIN_SHUTTER = 21;
int PIN_FOCUS = 20;

int main(int argc, char** argv) {
  
  if (argc!=4){
    std::cout << "Not enought arguments: 3 required\n";
    exit(0);
  }
  
  if (gpioInitialise() < 0) {
	  std::cout << "Error: setup pigpio.h fail\n";
	  return 1;
	} else {
		std::cout << "Setup pigpio\n";
	}
	
	gpioSetMode(PIN_SHUTTER, PI_OUTPUT);
	gpioSetMode(PIN_FOCUS, PI_OUTPUT);
	
	float t_pose = std::stof(argv[1]);
	float nb_photo = std::stoi(argv[2]);
	float wait = std::stof(argv[3]);
	
	std::cout << "temps de pose = " << t_pose << " s, nombre de photo = " << nb_photo << ", enregistrement = " << wait << "s\n";

	gpioWrite(PIN_FOCUS, true);
	usleep(OFFSET_t/2);
	gpioWrite(PIN_FOCUS, false);
	usleep(OFFSET_t);
	long t = long(t_pose * 1000000.0);
	
	for (int i=0; i<nb_photo; i++){
		std::cout << "Photo n°" << i+1 << " : temps de pose = " << t_pose << "\n";
		gpioWrite(PIN_SHUTTER, true);
		gpioWrite(PIN_FOCUS, true);
		usleep(OFFSET_t);
		usleep(t);
		gpioWrite(PIN_SHUTTER, false);
		gpioWrite(PIN_FOCUS, false);
		std::cout << "Low\n";
		usleep(wait * 1000000.0);
	}

	
	gpioTerminate();
	printf("pigpio terminate\n");
  return 0;
}




  

