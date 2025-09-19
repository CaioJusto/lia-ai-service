#!/usr/bin/env python3
"""
Teste básico do Lia AI Service
"""

import requests
import json
import time
from datetime import datetime

# Configuração
BASE_URL = "http://localhost:8000"
TEST_USER_ID = "test_user_123"
TEST_CONVERSATION_ID = f"test_conv_{int(time.time())}"

def test_health_check():
    """Teste do health check"""
    print("🏥 Testando health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check OK: {data['status']}")
            return True
        else:
            print(f"❌ Health check falhou: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erro no health check: {e}")
        return False

def test_chat():
    """Teste do chat com Lia"""
    print("\n💬 Testando chat com Lia...")
    
    try:
        payload = {
            "message": "Olá Lia! Você pode me explicar o que é fotossíntese?",
            "conversation_id": TEST_CONVERSATION_ID,
            "user_id": TEST_USER_ID
        }
        
        response = requests.post(f"{BASE_URL}/chat", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Chat funcionando!")
                print(f"📝 Resposta da Lia: {data['response'][:100]}...")
                return True
            else:
                print(f"❌ Chat falhou: {data.get('error')}")
                return False
        else:
            print(f"❌ Chat falhou: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no chat: {e}")
        return False

def test_flashcards():
    """Teste de geração de flashcards"""
    print("\n📚 Testando geração de flashcards...")
    
    try:
        payload = {
            "topic": "Sistema Solar",
            "difficulty": "medium",
            "count": 3,
            "user_id": TEST_USER_ID
        }
        
        response = requests.post(f"{BASE_URL}/generate-flashcards", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Flashcards gerados!")
                print(f"📝 Dados: {str(data['data'])[:100]}...")
                return True
            else:
                print(f"❌ Flashcards falharam: {data.get('error')}")
                return False
        else:
            print(f"❌ Flashcards falharam: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro nos flashcards: {e}")
        return False

def test_quiz():
    """Teste de geração de quiz"""
    print("\n🧠 Testando geração de quiz...")
    
    try:
        payload = {
            "topic": "História do Brasil",
            "difficulty": "easy",
            "question_count": 2,
            "user_id": TEST_USER_ID
        }
        
        response = requests.post(f"{BASE_URL}/generate-quiz", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Quiz gerado!")
                print(f"📝 Dados: {str(data['data'])[:100]}...")
                return True
            else:
                print(f"❌ Quiz falhou: {data.get('error')}")
                return False
        else:
            print(f"❌ Quiz falhou: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no quiz: {e}")
        return False

def test_study_plan():
    """Teste de geração de plano de estudos"""
    print("\n📅 Testando geração de plano de estudos...")
    
    try:
        payload = {
            "subject": "Matemática Básica",
            "duration_weeks": 2,
            "hours_per_day": 1,
            "user_id": TEST_USER_ID
        }
        
        response = requests.post(f"{BASE_URL}/generate-study-plan", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Plano de estudos gerado!")
                print(f"📝 Dados: {str(data['data'])[:100]}...")
                return True
            else:
                print(f"❌ Plano de estudos falhou: {data.get('error')}")
                return False
        else:
            print(f"❌ Plano de estudos falhou: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no plano de estudos: {e}")
        return False

def main():
    """Executar todos os testes"""
    print("🧪 Iniciando testes do Lia AI Service...")
    print(f"🌐 URL Base: {BASE_URL}")
    print(f"👤 User ID: {TEST_USER_ID}")
    print(f"💬 Conversation ID: {TEST_CONVERSATION_ID}")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health_check),
        ("Chat com Lia", test_chat),
        ("Geração de Flashcards", test_flashcards),
        ("Geração de Quiz", test_quiz),
        ("Plano de Estudos", test_study_plan),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro no teste {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumo dos resultados
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! O serviço está funcionando perfeitamente.")
    else:
        print("⚠️  Alguns testes falharam. Verifique a configuração e os logs.")

if __name__ == "__main__":
    main()
