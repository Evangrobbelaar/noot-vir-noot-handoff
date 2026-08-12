//****************************************************************************
//                            Janus Game Controller                          *
//****************************************************************************
//         Filename         : GameController_00a.cpp
//         Program          :
//         Description      :
//         Date Created     : 2025/01/13
//         Date        Author       Rev               Detail
//         2025/01/13    D.S.B.        0.00a            In Development
//            Basic program with fixed SSID & Password
//
//
//****************************************************************************
//--------------------------------Include Files-------------------------------
//****************************************************************************
// #include <Adafruit_GFX.h>    
// #include <Adafruit_ST7789.h> // Hardware-specific library for ST7789
// #include <TFT_eSPI.h>
// #include <SPI.h>
#include <stdint.h>
#include <SD.h>
#include <WiFi.h>
#include <BluetoothSerial.h>
#include <Preferences.h>
//****************************************************************************
//--------------------------Project & Version Control-------------------------
//****************************************************************************
#define Project     166
#define Version     0
#define SubVersion  0
#define Release     'c'
#define SubRelease  'a'
#define VersionHW   0
//****************************************************************************
//------------------------------Modifications---------------------------------
//****************************************************************************
//
//
//****************************************************************************
//-----------------------------Project Definitions----------------------------
//****************************************************************************



#define EnableBackLightTimer        1

#define ACTIVATE_BLUE_TOOTH         35

#define LED_HB                      16

#define LED_A                       33
#define LED_B                       25
#define LED_C                       26
#define LED_D                       27

#define LED_MAIN                    12

#define LED_BACK_LIGHT              4
#define TOUCH_IRQ                   5

#define USART_1_RXD                 14
#define USART_1_TXD                 13

#define RX_BUFF_SIZE_USART_0        64
#define RX_BUFF_SIZE_USART_1        64

#define MAX_SAMPLE_COUNT            5000

#define SECONDS_PER_MINUTE			    60
#define MINUTES_PER_HOUR		        60

#define LCD_BACKLIGHT_MINUTES       2 * SECONDS_PER_MINUTE

HardwareSerial USART_1(1);   // Define a Serial port instance called 'UART_MUX' using serial port 1

int LedState = LOW;          // ledState used to set the LED

uint16_t RxBuffIndexUSART_0 = 0, RxBuffIndexUSART_1 = 0;

char RxBufferUSART_0[RX_BUFF_SIZE_USART_0], RxBufferUSART_1[RX_BUFF_SIZE_USART_1], *fpos;
char aKey[6], aButtonPressed[3], aCounterValue[12], aFlashSize[16], aTxBuffer[32], aSerialNo[6];
uint16_t TimerUSART_0 = 0, TimerUSART_1 = 0, BackLightTimer = 0;
    //, iTimerLowLP = 0, iTimerIgnoreInputs = 0, iTimerEC = 0, iFilterStatus = 0, iTimerStartup;
uint32_t mSecCounter = 0;

//uint16_t UsartTimer = 0, BackLightTimer = 0;

bool bTimer = false, bDataReadyUSART_0, bDataReadyUSART_1, bTouchDetected, bConnectedToServer;

static const uint16_t timer_divider = 80;
//static const uint64_t timer_max_count = 1000000;
static const uint64_t timer_max_count = 1000;

// static char TxBufferMQTT[300], aWifiConnectionFailCounter[5];
// uint8_t WifiConnectAttemptCounter = 0, iWifiConnectionFailCounter = 0;

static hw_timer_t *timer = NULL;

// const char* ssid = "Buitewereld";
// const char* password = "Papaja01";
// const char* host = "192.168.3.69"; // Replace with your server's address

BluetoothSerial SerialBT;
Preferences preferences;

// Config structure
struct Config 
{
    char wifi_ssid[32];
    char wifi_password[64];
    char server_ip[16];
    uint16_t server_port;
    uint16_t SerialNo;
    bool configured;
};

Config config;
WiFiClient client;

void IRAM_ATTR onTimer();
void SerialEvent(void);
void USART_1_Event(void);
void SetupWifi();
bool ConnectToServer();
void LoadConfig();
void SaveConfig();
void HandleBluetoothConfig();
bool ConnectWiFi();
void ResetConfig();

// Colour values are swapped thus new colours are defined here
// Note values do not correspond with the actual hex value of that specific colour
#define TFT_GREY 0x1717
#define TFT_PURPLE 0x6E67
#define TFT_CYAN 0x00F3
#define TFT_GREEN 0xF81F
#define TFT_BLUE 0x07FF
#define TFT_RED 0xFF00
#define TFT_BLACK 0xFFFF
#define TFT_WHITE 0x0000

#define center_x 120

//TFT_eSPI tft = TFT_eSPI();

void setup() 
{
  Serial.begin(115200);
  Serial.println("Controller started...");

  uint64_t chipid = ESP.getEfuseMac();
  delay(150);
  Serial.print("\nESN: ");
  Serial.println(chipid);   
  delay(150);

  uint32_t FlashSize = ESP.getFlashChipSize();
  sprintf(aFlashSize, "%d", FlashSize);
  Serial.print("Flash size: ");
  Serial.print(aFlashSize);
  Serial.println(" bytes");
  delay(100);

    // Initialize preferences
    if(!preferences.begin("wifi-config", false)) 
    {
        Serial.println("Failed to initialize Preferences");
    }

  // Connect to Wi-Fi
  // WiFi.begin(ssid, password);
  // Serial.println("Connecting to WiFi...");
  // while (WiFi.status() != WL_CONNECTED) 
  //   {
  //     delay(500);
  //     Serial.print(".");
  //   }
  // Serial.println("\nWiFi connected!");


  pinMode(LED_HB, OUTPUT);
  pinMode(LED_A, OUTPUT);
  pinMode(LED_B, OUTPUT);
  pinMode(LED_C, OUTPUT);
  pinMode(LED_D, OUTPUT);
  pinMode(LED_MAIN, OUTPUT);
  pinMode(LED_BACK_LIGHT, OUTPUT);
  pinMode(TOUCH_IRQ, INPUT); 
  pinMode(ACTIVATE_BLUE_TOOTH, INPUT); 

  

//   tft.init(); // Initializing TFT screen
//   tft.setRotation(0);
//   tft.fillScreen(TFT_BLACK);
//   tft.setTextSize(5);
//   tft.setTextColor(TFT_WHITE);
//   digitalWrite(LED_BACK_LIGHT, HIGH); // Back light switched on
//   tft.setRotation(1);
// //  tft.setTextColor(TFT_BLUE);
//   tft.setTextColor(TFT_CYAN);
//   tft.drawString("GAME", 100, 70);
//   tft.drawString("CONTROLLER", 10, 150);
  delay(3500);

  USART_1.begin(9600, SERIAL_8N1, USART_1_RXD, USART_1_TXD);         // Define and start Sender serial port
  delay(100);

  // Create and start timer (num, divider, countUp)
  timer = timerBegin(0, timer_divider, true);

  // Provide ISR to timer (timer, function, edge)
  timerAttachInterrupt(timer, &onTimer, true);

  // At what count should ISR trigger (timer, count, autoreload)
  timerAlarmWrite(timer, timer_max_count, true);

  // Allow ISR to trigger
  timerAlarmEnable(timer);

  BackLightTimer = LCD_BACKLIGHT_MINUTES;   
    digitalWrite(LED_A, HIGH);
    digitalWrite(LED_B, HIGH);
    digitalWrite(LED_C, HIGH);
    digitalWrite(LED_D, HIGH);  

    // Check if device is configured
    LoadConfig();
    
    if (!config.configured) 
    {
        Serial.println("No configuration found. Starting Bluetooth configuration mode...");
        SerialBT.begin("ESP32-Config"); // Bluetooth device name
        HandleBluetoothConfig();
    }
    
    // Try to connect to WiFi
    if (!ConnectWiFi()) 
    {
        Serial.println("Failed to connect to WiFi. Reverting to Bluetooth config mode...");
        SerialBT.begin("ESP32-Config");
        HandleBluetoothConfig();
        return;
    }
    
    // Try to connect to server
    if (!ConnectToServer()) 
    {
        Serial.println("Failed to connect to server");
    }    
}

void loop() 
{
  if(bTimer)
    {
      bTimer = false; 
      digitalWrite(LED_HB, LOW);
      delay(50);
      digitalWrite(LED_HB, HIGH);  
      if (!digitalRead(ACTIVATE_BLUE_TOOTH))
        {
          USART_1.print(char(231));
          USART_1.print("Buzz");          
          USART_1.print(char(5));
          delay(200);
          SerialBT.begin("ESP32-Config"); // Bluetooth device name
          HandleBluetoothConfig();          
        }
    }
  if (Serial.available())
    {
        SerialEvent();
    }  
    
  if (USART_1.available())
    {
        USART_1_Event();     
    }     

  if(bDataReadyUSART_1)
    {
      bDataReadyUSART_1 = 0;
      Serial.println(RxBufferUSART_1);
//ç|EMS|D|1229|    aKey[6], aButtonPressed[3], aCounterValue[12],
      if (RxBufferUSART_1[0] == char(231))
        {
              char *Key_1 = strtok(RxBufferUSART_1, "|");
              char *Key_2 = strtok(NULL, "|");
              char *Key_3 = strtok(NULL, "|");
              char *Key_4 = strtok(NULL, "|");
              char Result = 0;    
              memset(aKey, 0, sizeof(aKey));
              memset(aButtonPressed, 0, sizeof(aButtonPressed));  
              memset(aCounterValue, 0, sizeof(aCounterValue));  

              strcpy(aKey, Key_2);
              strcpy(aButtonPressed, Key_3);
              strcpy(aCounterValue, Key_4);
              Serial.print("\naKey: ");
              Serial.println(aKey);
              Serial.print("\naButtonPressed: ");
              Serial.println(aButtonPressed);
              Serial.print("\naCounterValue: ");
              Serial.println(aCounterValue);   
                                       
              memset(aTxBuffer, 0, sizeof(aTxBuffer));
              aTxBuffer[0] = 231;
              strcat(aTxBuffer, "|EMS|");
              sprintf(aSerialNo, "%d", config.SerialNo);
              strcat(aTxBuffer, aSerialNo);
              strcat(aTxBuffer, "|");
              strcat(aTxBuffer, aButtonPressed);
              strcat(aTxBuffer, "|");
              strcat(aTxBuffer, aCounterValue);
              strcat(aTxBuffer, "|");              
              if (RxBufferUSART_1[6] == 'A')
                digitalWrite(LED_A, HIGH);
              if (RxBufferUSART_1[6] == 'B')
                digitalWrite(LED_B, HIGH);
              if (RxBufferUSART_1[6] == 'C')
                digitalWrite(LED_C, HIGH);
              if (RxBufferUSART_1[6] == 'D')
                digitalWrite(LED_D, HIGH);
              Serial.println(aTxBuffer);
              client.println(aTxBuffer);
        }
      memset(RxBufferUSART_1, 0, sizeof(RxBufferUSART_1));
      RxBuffIndexUSART_1 = 0; 
    }       
 
  if (!client.connected())     // Reconnect if connection is lost
  {
    Serial.println("Disconnected from server. Reconnecting...");
    bConnectedToServer = 0;
    digitalWrite(LED_A, HIGH);
    digitalWrite(LED_B, HIGH);
    digitalWrite(LED_C, HIGH);
    digitalWrite(LED_D, HIGH);
    digitalWrite(LED_MAIN, LOW);
    ConnectToServer();    
  }

  if (client.available())       // Check for incoming data from the server
  {
    char aMessageFromServer[50];
    String MessageFromServer = client.readStringUntil('\n'); // Read incoming message until newline
    USART_1.print(char(231));
    USART_1.print(MessageFromServer);
    strcpy(aMessageFromServer, MessageFromServer.c_str());
    fpos = strstr(aMessageFromServer, "READY");
    if (fpos)
        {
          digitalWrite(LED_A, LOW);
          digitalWrite(LED_B, LOW);
          digitalWrite(LED_C, LOW);
          digitalWrite(LED_D, LOW);
        }  
    Serial.println("Message from server: " + MessageFromServer);
  }
  delay(10); // Small delay to avoid excessive CPU usage
}

// void ConnectToServer() 
// {
//   Serial.printf("Connecting to %s:%d...\n", host, port);
//   while (!client.connect(host, port)) 
//   {
//     Serial.println("Connection failed. Retrying...");
//     delay(1000);
//   }
//   Serial.println("Connected to server!");
//   bConnectedToServer = 1;
//   digitalWrite(LED_MAIN, HIGH);
// }

bool ConnectToServer() 
{
    Serial.printf("Connecting to server %s:%d\n", config.server_ip, config.server_port);
    if (client.connect(config.server_ip, config.server_port)) 
    {
        Serial.println("Connected to server");
        bConnectedToServer = 1;
        digitalWrite(LED_MAIN, HIGH);        
        return true;
    }
    Serial.println("Server connection failed");
    return false;
}

void IRAM_ATTR onTimer() 
{
  if(++mSecCounter > 1000)
    {
      mSecCounter = 0;
      bTimer = 1;
    }  

  if (TimerUSART_0)
    {
	    TimerUSART_0 ++;
	    if (TimerUSART_0 > 50)
	    {
		    TimerUSART_0 = 0;
		    bDataReadyUSART_0 = 1;
	    }
    }
  if (TimerUSART_1)
    {
	    TimerUSART_1 ++;
	    if (TimerUSART_1 > 150)
	    {
		    TimerUSART_1 = 0;
		    bDataReadyUSART_1 = 1;
	    }
    } 
}

void SerialEvent(void) 
{
  char inChar = (char)Serial.read();
  RxBufferUSART_0[RxBuffIndexUSART_0++] = inChar;
  TimerUSART_0 = 1;
}

void USART_1_Event(void) 
{
  char inCharUSART_1 = (char)USART_1.read();
  RxBufferUSART_1[RxBuffIndexUSART_1++] = inCharUSART_1;
  TimerUSART_1 = 1;
}

// void SetupWifi()     // Connect to WiFi network
// {
//   Serial.print("\nConnecting to ");
//   Serial.println(ssid);

//   WiFi.begin(ssid, password); // Connect to network
// /*
//   while (WiFi.status() != WL_CONNECTED)     // Wait for connection
//   { 
//     delay(500);
//     Serial.print(".");
//   }
// */
//     Serial.println("Connecting to WiFi");
//     while (WiFi.status() != WL_CONNECTED)
//     {
//       delay(500);
//       Serial.print(".");
//       if (WifiConnectAttemptCounter++ > 20)
//         {
//           Serial.println("\nConnection Unsucessful...");
//           iWifiConnectionFailCounter++;
//           delay(150);
//           Serial.print("WifiConnectionFailCounter: ");
//           Serial.println(aWifiConnectionFailCounter);
//         }        
//     }
//   Serial.println();
//   Serial.println("WiFi connected");
//   Serial.print("IP address: ");
//   Serial.println(WiFi.localIP());
// }

bool ConnectWiFi() 
{
    Serial.printf("Connecting to WiFi %s\n", config.wifi_ssid);
    WiFi.begin(config.wifi_ssid, config.wifi_password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) 
    {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    Serial.println();
    
    if (WiFi.status() == WL_CONNECTED) 
    {
        Serial.printf("Connected to WiFi. IP: %s\n", WiFi.localIP().toString().c_str());
        return true;
    }
    return false;
}

void LoadConfig() 
{
    config.configured = preferences.getBool("configured", false);
    Serial.printf("Config status: %d\n", config.configured);
    
    if (config.configured) 
    {
        String ssid = preferences.getString("ssid", "");
        String password = preferences.getString("password", "");
        String server = preferences.getString("server_ip", "");
        
        ssid.toCharArray(config.wifi_ssid, sizeof(config.wifi_ssid));
        password.toCharArray(config.wifi_password, sizeof(config.wifi_password));
        server.toCharArray(config.server_ip, sizeof(config.server_ip));
        config.server_port = preferences.getUInt("server_port", 0);
        config.SerialNo = preferences.getUInt("SerialNo", 0);
        
        Serial.println("Loaded configuration:");
        Serial.printf("SSID: %s\n", config.wifi_ssid);
        Serial.printf("Server IP: %s\n", config.server_ip);
        Serial.printf("SerialNo: %d\n", config.SerialNo);                
        Serial.printf("Port: %d\n", config.server_port);
    }
}

void SaveConfig() 
{
  //  preferences.clear(); // Clear existing preferences
    
    preferences.putBool("configured", true);
    preferences.putString("ssid", String(config.wifi_ssid));
    preferences.putString("password", String(config.wifi_password));
    preferences.putString("server_ip", String(config.server_ip));
    preferences.putUInt("server_port", config.server_port);
    preferences.putUInt("SerialNo", config.SerialNo);
    
    Serial.println("Saving configuration:");
    Serial.printf("SSID: %s\n", config.wifi_ssid);
    Serial.printf("Server IP: %s\n", config.server_ip);
    Serial.printf("Port: %d\n", config.server_port);
    Serial.printf("SerialNo: %d\n", config.SerialNo);
    
    // Verify the save
    bool saved = preferences.getBool("configured", false);
    Serial.printf("Save verification - configured: %d\n", saved);
}

void HandleBluetoothConfig() 
{
    Serial.println("Entering Bluetooth configuration mode");
    
    while (true) 
    {
        if (SerialBT.available()) 
        {
            String command = SerialBT.readStringUntil('\n');
            command.trim();
            
            Serial.printf("Received command: %s\n", command.c_str());
            
            // Handle SAVE command (both with and without colon)
            if (command == "SAVE" || command == "SAVE:") 
            {
                SerialBT.println("Saving configuration...");
                SaveConfig();
                SerialBT.println("Configuration saved");
                SerialBT.println("Restarting...");
                Serial.println("Configuration saved, restarting...");
                delay(1000);
                ESP.restart();
                continue;
            }
            else if (command == "STATUS" || command == "STATUS:") 
            {
                SerialBT.println("\nCurrent Configuration:");
                SerialBT.println("--------------------");
                SerialBT.printf("SSID: %s\n", config.wifi_ssid);
//                SerialBT.printf("PASSWORD: %s\n", config.wifi_password);
                SerialBT.printf("Server IP: %s\n", config.server_ip);
                SerialBT.printf("Port: %d\n", config.server_port);
                SerialBT.printf("SerialNo: %d\n", config.SerialNo);                
                SerialBT.println("--------------------");
                continue;
            }
            else if (command == "RESET" || command == "RESET:") 
            {
                SerialBT.println("Resetting all configuration...");
                preferences.clear();
                config.configured = false;
                memset(config.wifi_ssid, 0, sizeof(config.wifi_ssid));
                memset(config.wifi_password, 0, sizeof(config.wifi_password));
                memset(config.server_ip, 0, sizeof(config.server_ip));
                config.server_port = 0;
                SerialBT.println("Configuration reset complete");
                SerialBT.println("Restarting...");
                delay(1000);
                ESP.restart();
                continue;            
            }
            else if (command == "HELP" || command == "HELP:") 
            {
                SerialBT.println("\nAvailable Commands:");
                SerialBT.println("--------------------");
                SerialBT.println("SSID:your_wifi_name");
                SerialBT.println("PASS:your_wifi_password");
                SerialBT.println("SERVER:Server IP Address");
                SerialBT.println("PORT:Port");
                SerialBT.println("SN:Serial Number");
                SerialBT.println("STATUS - Show current config");
                SerialBT.println("RESET - Clear all settings");
                SerialBT.println("SAVE - Save and restart");
                SerialBT.println("HELP - Show this message");
                SerialBT.println("--------------------");
                continue;
            }            
            // Handle other commands that require parameters
            int separatorIndex = command.indexOf(':');
            if (separatorIndex != -1) 
            {
                String cmd = command.substring(0, separatorIndex);
                String value = command.substring(separatorIndex + 1);
                
                if (cmd == "SSID") 
                {
                    value.toCharArray(config.wifi_ssid, sizeof(config.wifi_ssid));
                    SerialBT.println("SSID set");
                    Serial.printf("SSID set to: %s\n", config.wifi_ssid);
                }
                else if (cmd == "PASS") 
                {
                    value.toCharArray(config.wifi_password, sizeof(config.wifi_password));
                    SerialBT.println("Password set");
                    Serial.println("Password set");
                }
                else if (cmd == "SERVER") 
                {
                    value.toCharArray(config.server_ip, sizeof(config.server_ip));
                    SerialBT.println("Server IP set");
                    Serial.printf("Server IP set to: %s\n", config.server_ip);
                }
                else if (cmd == "PORT") 
                {
                    config.server_port = value.toInt();
                    SerialBT.println("Port set");
                    Serial.printf("Port set to: %d\n", config.server_port);
                }
                else if (cmd == "SN") 
                {
                    config.SerialNo = value.toInt();
                    SerialBT.println("SerialNo set");
                    Serial.printf("SerialNo set to: %d\n", config.SerialNo);
                }                
            }
        }
        delay(10);
    }
}

void ResetConfig() 
{
    preferences.clear();
    config.configured = false;
}
