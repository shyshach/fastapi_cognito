from typing import Optional
import subprocess
import boto3
import uvicorn
from pydantic import BaseModel
from fastapi import Depends, FastAPI
import json
from web3 import Web3, HTTPProvider
from eth_account import Account
from auth import jwks, get_current_user
from JWTBearer import JWTBearer

app = FastAPI()
truffle_path = "/home/rostyslavshymchak/PycharmProjects/cryptoproject/metacoin"
blockchain_address = 'HTTP://localhost:8545'
web3 = Web3(HTTPProvider(blockchain_address))
contract = ''
contract_abi = ''
contract_address = ''
auth = JWTBearer(jwks)


class Item(BaseModel):
    name: str
    price: float
    owner: str


class Transaction(BaseModel):
    sender: str
    receiver: str
    amount: int


class EthTransaction(BaseModel):
    sender: str
    sender_private_key: str
    receiver: str
    amount: int


class UserCredentials(BaseModel):
    access_token: str
    refresh_token: str
    session_token: str


#@app.on_event("startup")
async def startup_event():
    subprocess.check_call(['truffle', 'migrate', ""], cwd=truffle_path)
    web3.eth.defaultAccount = web3.eth.accounts[0]
    with open("../cryptoproject/metacoin/build/contracts/MetaCoin.json", "r") as contract_json:
        contract_dict = json.load(contract_json)
        global contract_address
        global contract_abi
        contract_address = contract_dict["networks"]["5777"]["address"]
        contract_abi = contract_dict['abi']
        print(contract_address)
    global contract
    contract = web3.eth.contract(abi=contract_abi,
                                 address=Web3.toChecksumAddress(contract_address))
    # process = subprocess.Popen(['truffle ', '-a'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=truffle_path)
    # out, err = process.communicate()


@app.post("/items")
def send_transaction(item: Transaction):
    message = contract.functions.sendCoin(Web3.toChecksumAddress(item.receiver), item.amount). \
        transact({"from": Web3.toChecksumAddress(item.sender)})
    balance = contract.functions.getBalance(Web3.toChecksumAddress(item.receiver)).call()
    receipt = web3.eth.waitForTransactionReceipt(message)
    print(item.receiver, item.amount, message, balance, dict(receipt))
    return {"sender": item.sender, "receiver": item.receiver, "amount": balance}


@app.post("/add_user")
def reset_balances(address: str):
    accounts = web3.eth.accounts
    account1 = Account.create()
    accounts.append(account1)
    print(accounts)
    accounts = web3.eth.accounts
    print(accounts)
    # balance = contract.functions.editBalance(Web3.toChecksumAddress(account1), 100).transact()
    # balance = contract.functions.getBalance(Web3.toChecksumAddress(account1)).call()
    return {"ss": account1}


@app.post("/transact", dependencies=[Depends(auth)])
def transact_in_eth(item: EthTransaction) -> str:
    gas_price = web3.eth.gas_price
    signed_tx = web3.eth.account.signTransaction({'to': Web3.toChecksumAddress(item.receiver),
                                                  'from': Web3.toChecksumAddress(item.sender),
                                                  'value': item.amount,
                                                  'nonce': web3.eth.getTransactionCount(
                                                      Web3.toChecksumAddress(item.sender)),
                                                  'gas': 2000000,
                                                  'gasPrice': gas_price
                                                  }, item.sender_private_key)
    tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
    receipt = web3.eth.waitForTransactionReceipt(tx_hash)
    return str(Web3.toJSON(receipt))


@app.get("/accounts")
def get_accounts():
    return {"accounts": web3.eth.accounts}


@app.get("/secure", dependencies=[Depends(get_current_user)])
async def secure(username=Depends(get_current_user)):
    return username


@app.post("/add_user_to_cognito")
def create_user(username: str, password: str,
                user_pool_id: str, app_client_id: str) -> None:
    client = boto3.client('cognito-idp')

    # # initial sign up
    # resp = client.sign_up(
    #     ClientId=app_client_id,
    #     Username=username,
    #     Password=password,
    #     UserAttributes=[
    #         {
    #             'Name': 'email',
    #             'Value': 'test@test.com'
    #         },
    #     ]
    # )
    client.admin_set_user_password(
        UserPoolId="us-east-1_3BPxwDb6P",
        Username="petro1",
        Password="Qwertyu-012",
        Permanent=True
    )

    # then confirm signup
    resp = client.admin_confirm_sign_up(
        UserPoolId=user_pool_id,
        Username=username
    )

    print("User successfully created.")


@app.post("/login")
def login(username: str, password: str, user_pool_id: str, app_client_id: str):
    client = boto3.client('cognito-idp')
    # user_id - 5427213k9qd1vrgcir1ao9mjar
    # pool_id -us-east-1_3BPxwDb6P

    resp = client.admin_initiate_auth(
        UserPoolId=user_pool_id,
        ClientId=app_client_id,
        AuthFlow='ADMIN_NO_SRP_AUTH',
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": password
        }
    )
    access = resp['AuthenticationResult']['AccessToken']
    refresh = resp["AuthenticationResult"]["RefreshToken"]
    print("Access token:", access, "  refresh token: ", refresh)
    print("ID token:", resp['AuthenticationResult']['IdToken'])
    return {"acces": access, "refresh": refresh, "id_token": resp['AuthenticationResult']['IdToken']}


@app.post("/refresh_tokens")
def refresh_tokens(refresh_token: str, client_id: str):
    client = boto3.client('cognito-idp')
    resp = client.initiate_auth(
        ClientId=client_id,
        AuthFlow='REFRESH_TOKEN_AUTH',
        AuthParameters={
            "REFRESH_TOKEN": refresh_token
        }
    )
    return resp["AuthenticationResult"]


if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
