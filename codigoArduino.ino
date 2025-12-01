#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <Adafruit_I2CDevice.h>

Adafruit_PWMServoDriver pwmDriver = Adafruit_PWMServoDriver();

#define SERVO_FREQ 50 // Analog servos run at ~50 Hz updates

// Motor de passos da junta prismatica
#define dirPin2 4
#define stepPin2 7
#define enPin2 9

#define dirPin1 5
#define stepPin1 6
#define enPin1 8

#define stepsPerRevolution 400

#define GARRA_ON 650
#define GARRA_GIRA 2150
#define GARRA_ABRE 1500
#define GARRA_FECHA 900
#define GARRA_PEGA 1120

int command;
bool isCalibrated = 0;
float currPos;
int sensor_direita = 2;
int sensor_esquerda = 3;

float rest[] = {0, 0, 135, -96, -89};       //Posição Home
float pega[] = {65, 0, 50, -75, -10};
float prepara[] = {45, 0, 50, -75, -10};
float caixa1[] = {62, 90, 60, -96, -20};      //Posição Caixa 1
float caixa2[] = {40, 95, 60, -96, -20};      //Posição Caixa 2
float caixa3[] = {10, 95, 60, -96, -20};      //Posição Caixa 3
float caixa4[] = {40, -90, 135, -96, -70};    //Posição Caixa 4
float caixa5[] = {225, 19.44, -11.96, -75};   //Posição Caixa 5
float caixa6[] = {62, -95, 50, -75, -10};     //Posição Caixa 6
int pwm[6];
float angles[6];
float currAngles[6];

uint8_t servonum0 = 0;
uint8_t servonum1 = 1;
uint8_t servonum2 = 11;
uint8_t servonum3 = 3;
uint8_t servonum4 = 12;
uint8_t servonum5 = 5;

enum States {
    ESPERANDO_COMANDO,
    CALIBRADO,
    MOVENDO_PRISMA,
    PEGANDO_PECA,
    PREPARA_PECA,
    PEGA_PECA,
    SELECT_CAIXA,
    GET_COLORS,
    SET_HOME,
    PARA_TUDO,

};

States currState = ESPERANDO_COMANDO;

void get_pwm(float angle[], int size, int pwmf[], float curr[]) {
  int Pm[6];
  int pwmi[6];
  pwmf[0] = 1500 - ((25 * angle[5]) / 3);   //REVER A EQUAÇÃO
  pwmf[1] = 1350 - ((750 * angle[4]) / 90);  
  pwmf[2] = 1400 - ((900 * angle[3]) / 90);
  pwmf[3] = 1000 - ((1500 * angle[2]) / 180);
  pwmf[4] = 500 + ((2000 * angle[1]) / 180);
  pwmf[5] = 1400 - ((1540 * angle[0]) / 180);

  pwmi[0] = 1500 - ((25 * curr[5]) / 3);  //REVER A EQUAÇÃO
  pwmi[1] = 1350 - ((750 * curr[4]) / 90);  
  pwmi[2] = 1400 - ((900 * curr[3]) / 90);
  pwmi[3] = 1000 - ((1500 * curr[2]) / 180);
  pwmi[4] = 500 + ((2000 * curr[1]) / 180);
  pwmi[5] = 1400 - ((1540 * curr[0]) / 180);

  if(currState == CALIBRADO && !isCalibrated){
    pwmDriver.writeMicroseconds(servonum5, pwmf[5]);
    pwmDriver.writeMicroseconds(servonum4, pwmf[4]);
    pwmDriver.writeMicroseconds(servonum3, pwmf[3]);
    pwmDriver.writeMicroseconds(servonum2, pwmf[2]);
  }
  else{
    for (int stp = 0; stp<=5; stp++){
      Pm[5] = pwmi[5] + (pwmf[5]-pwmi[5])*stp/5;
      pwmDriver.writeMicroseconds(servonum5, Pm[5]);
      delay(100);
    }                                                //REVER A ORDEM AQUI
    for (int stp = 0; stp<=10; stp++){
      Pm[2] = pwmi[2] + (pwmf[2]-pwmi[2])*stp/10;
      pwmDriver.writeMicroseconds(servonum2, Pm[2]);
      delay(100);
      Pm[3] = pwmi[3] + (pwmf[3]-pwmi[3])*stp/10;
      pwmDriver.writeMicroseconds(servonum3, Pm[3]);
      delay(100);
      Pm[4] = pwmi[4] + (pwmf[4]-pwmi[4])*stp/10;
      pwmDriver.writeMicroseconds(servonum4, Pm[4]);
      delay(100);
    }      
  }
}

int move_joints(float t1, float t2, float t3, float t4){
  delay(10); 
  float goToAngles[] = {t1, t2, t3, t4};
  get_pwm(goToAngles, 4, pwm, currAngles);
  delay(100);
  return 1;
}

int move_prism(float quant, float y, float atualPos){
  float move;
  float new_y;
  float max_value;
  int dect_sensorD = digitalRead(sensor_direita);
  int dect_sensorE = digitalRead(sensor_esquerda);
  if (quant == 0){
    if(atualPos < y){
      move = y - atualPos;
      digitalWrite(dirPin2, LOW);
      max_value = 0.804*move;
      for(int j = 0; j < max_value; j++){
        for (int i = 0; i < stepsPerRevolution; i++) {
        //These four lines result in 1 step:
          digitalWrite(stepPin2, HIGH);
          delayMicroseconds(100);
          digitalWrite(stepPin2, LOW);
          delayMicroseconds(100);
          dect_sensorD = digitalRead(sensor_direita);
          if(!dect_sensorD){
            i = stepsPerRevolution;
            j = max_value;
          }
        }
      }
    }
    if(atualPos > y){
      move = atualPos - y;
      digitalWrite(dirPin2, HIGH);
      max_value = 0.804*move;
      for(int j = 0; j < max_value; j++){
        for (int i = 0; i < stepsPerRevolution; i++) {
        //These four lines result in 1 step:
          digitalWrite(stepPin2, HIGH);
          delayMicroseconds(100);
          digitalWrite(stepPin2, LOW);
          delayMicroseconds(100);
          dect_sensorE = digitalRead(sensor_esquerda);
          if(!dect_sensorE){
            i = stepsPerRevolution;
            j = max_value;
          }
        }
      }
    }
    new_y = y;
  }
  else{
    digitalWrite(dirPin2, HIGH);
    //Spin the stepper motor 5 revolutions fast:
    for (int i = 0; i < stepsPerRevolution; i++) {
      //These four lines result in 1 step:
      digitalWrite(stepPin2, HIGH);
      delayMicroseconds(100);
      digitalWrite(stepPin2, LOW);
      delayMicroseconds(100);
    }
    new_y = 0;
  }
  currPos = new_y;
  return currPos;
}

int calibragem(){
  //Serial.println("Entrei Calibragem");
  move_joints(rest[1], rest[2], rest[3], rest[4]);
  for(int i = 1; i <= 4; i++){
    currAngles[i-1] = rest[i];
  }
  delay(100);
  int dect_sensor = digitalRead(sensor_esquerda);
  Serial.println(dect_sensor);
  while(dect_sensor){
    move_prism(1,0,0);
    delay(10);
    dect_sensor = digitalRead(sensor_esquerda);
    //Serial.println(dect_sensor);
  }
  isCalibrated = 1;
  return 0;
}

void setup() {
  Serial.begin(9600);

  pinMode(stepPin2, OUTPUT);
  pinMode(dirPin2, OUTPUT);
  pinMode(enPin2, OUTPUT);
  digitalWrite(enPin2, LOW);

  pinMode(stepPin1, OUTPUT);
  pinMode(dirPin1, OUTPUT);
  pinMode(enPin1, OUTPUT);
  digitalWrite(enPin1, LOW);
  digitalWrite(dirPin1, HIGH);

  pinMode(sensor_direita, INPUT_PULLUP);
  pinMode(sensor_esquerda, INPUT_PULLUP);

  pwmDriver.begin();
  pwmDriver.setOscillatorFrequency(27000000);
  pwmDriver.setPWMFreq(SERVO_FREQ);  // Analog servos run at ~50 Hz updates

  pwmDriver.writeMicroseconds(servonum0, GARRA_FECHA);
  pwmDriver.writeMicroseconds(servonum1, GARRA_ON);
  move_joints(rest[1],rest[2],rest[3], rest[4]);
  for(int i = 1; i <= 4; i++){
    currAngles[i-1] = rest[i];
  }

  while(command != 1){
    command = 0;
    Serial.println(command);
    delay(100);
    if(Serial.available() != 0){
      command = Serial.readStringUntil("\n").toInt();
    }
  }
  currState = CALIBRADO;
}

void loop() {
  switch(currState){
    case ESPERANDO_COMANDO:
      //Serial.print("Estado ESPERANDO_COMANDO: ");
      //Serial.println(currState);
      while(Serial.available() == 0){
          digitalWrite(stepPin1, HIGH);
          delayMicroseconds(500);
          digitalWrite(stepPin1, LOW);
          delayMicroseconds(500);
      }
      command = Serial.readStringUntil("\n").toInt();
      delay(100);
      if(command == 3){
        currState = MOVENDO_PRISMA;
      }
    break;

    case CALIBRADO:
      //Serial.print("Estado CALIBRADO: ");
      //Serial.println(currState);
      pwmDriver.writeMicroseconds(servonum0, GARRA_FECHA);
      pwmDriver.writeMicroseconds(servonum1, GARRA_ON);
      if (isCalibrated){
        //Serial.println("isCalibrated");
        move_joints(rest[1], rest[2], rest[3], rest[4]);
        for(int i = 1; i <= 4; i++){
          currAngles[i-1] = rest[i];
        }
      }
      else currPos = calibragem();
      delay(100);
      command = 2;
      Serial.println(command);
      delay(100);
      currState = ESPERANDO_COMANDO;
    break;

    case MOVENDO_PRISMA:
      //Serial.print("Estado MOVENDO_PRISMA: ");
      //Serial.println(currState);
      move_prism(0, pega[0], currPos);
      delay(10);
      command = 4;
      Serial.println(command);
      currState = PEGANDO_PECA;
    break;

    case PEGANDO_PECA:
      //Serial.print("Estado PEGANDO_PECA: ");
      //Serial.println(currState);
      while(Serial.available() > 0){
        String input = Serial.readStringUntil("\n");
        command = input.toFloat();
        if(command == 5){
          currState = PREPARA_PECA;
          break;
        }
      }
    break;

    case PREPARA_PECA:
      //Serial.print("Estado PREPARA_PECA: ");
      //Serial.println(currState);
      pwmDriver.writeMicroseconds(servonum0, GARRA_ABRE); //Garra abre total
      move_prism(0, prepara[0], currPos);
      move_joints(pega[1], pega[2], pega[3], pega[4]);
      for(int i = 1; i <= 4; i++){
        currAngles[i-1] = pega[i];
      }
      delay(100);
      currState = PEGA_PECA;
    break;

    case PEGA_PECA:
      //Serial.print("Estado PEGA_PECA: ");
      //Serial.println(currState);
      move_prism(0, pega[0], currPos); 
      delay(100);
      pwmDriver.writeMicroseconds(servonum0, GARRA_PEGA); //Garra fecha na peça
      delay(100);
      pwmDriver.writeMicroseconds(servonum2, 1900);
      currAngles[3] = -50;
      command = 6;
      Serial.println(command);
      currState = SELECT_CAIXA;
    break;

    case SELECT_CAIXA:
      //Serial.print("Estado SELECT_CAIXA: ");
      //Serial.println(currState);
      while(Serial.available() > 0){
        String input = Serial.readStringUntil("\n");
        command = input.toFloat();
        if(command < 70 || command < 80){
          currState = GET_COLORS;
          break;
        }
      }
    break;

    case GET_COLORS:
      //Serial.print("Estado GET_COLORS: ");
      //Serial.println(currState);
      if(command == 71){
        move_prism(0, caixa1[0], currPos);
        delay(100);
        move_joints(caixa1[1], caixa1[2], caixa1[3], caixa1[4]);
        for(int i = 1; i <= 4; i++){
          currAngles[i-1] = caixa1[i];
        }
        delay(100);
      }
      if(command == 72){
        move_prism(0, caixa2[0], currPos);
        delay(100);
        move_joints(caixa2[1], caixa2[2], caixa2[3], caixa2[4]);
        for(int i = 1; i <= 4; i++){
          currAngles[i-1] = caixa2[i];
        }
        delay(100);
      }
      if(command == 73){
        move_prism(0,caixa3[0],currPos);
        delay(100);
        move_joints(caixa3[1],caixa3[2],caixa3[3], caixa3[4]);
        for(int i = 1; i <= 4; i++){
          currAngles[i-1] = caixa3[i];
        }
        delay(100);
      }
      if(command == 74){
        move_prism(0,caixa4[0],currPos);
        delay(100);
        move_joints(caixa4[1],caixa4[2],caixa4[3], caixa4[4]);
        for(int i = 1; i <= 4; i++){
          currAngles[i-1] = caixa4[i];
        }
        delay(100);
      }
      if(command == 75){
        move_prism(0,caixa5[0],currPos);
        delay(100);
        move_joints(caixa5[1],caixa5[2],caixa5[3], caixa5[4]);
        for(int i = 1; i <= 4; i++){
          currAngles[i-1] = caixa5[i];
        }
        delay(100);
      }
      if(command == 76){
        move_prism(0,caixa6[0],currPos);
        delay(100);
        move_joints(caixa6[1],caixa6[2],caixa6[3], caixa6[4]);
        for(int i = 1; i <= 4; i++){
          currAngles[i-1] = caixa6[i];
        }
        delay(100);
      }
      command = 8;
      Serial.println(command);
      delay(100);
      while(Serial.available() == 0){}
        command = Serial.readStringUntil("\n").toInt();
        delay(100);
        if(command == 9){
          currState = SET_HOME;
        }
    break;

    case SET_HOME:
      //Serial.print("Estado SET_HOME: ");
      //Serial.println(currState);
      pwmDriver.writeMicroseconds(servonum1, GARRA_GIRA);
      delay(1000);
      pwmDriver.writeMicroseconds(servonum0, GARRA_ABRE); //Garra abre total
      command = 10;
      Serial.println(command);
      delay(100);
      while(Serial.available() == 0){}
        command = Serial.readStringUntil("\n").toInt();
        delay(100);
        if(command == 11){
          currState = CALIBRADO;
        }
    break;

    case PARA_TUDO:
      Serial.print("Estado PARA_TUDO: ");
      Serial.println(currState);
      while(Serial.available() == 0){}
        command = Serial.readStringUntil("\n").toInt();
        delay(100);
        if(command == 10){
          currState = ESPERANDO_COMANDO;
        }
    break;

    default:
      Serial.print("Estado DEFAULT: ");
      Serial.println(currState);
    break;

  }

}
