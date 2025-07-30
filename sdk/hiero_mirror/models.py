"""Pydantic models for Hiero Mirror Node API responses."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class Order(str, Enum):
    """Order enumeration for query parameters."""
    ASC = "asc"
    DESC = "desc"


class TransactionType(str, Enum):
    """Transaction type enumeration."""
    ATOMICBATCH = "ATOMICBATCH"
    CONSENSUSCREATETOPIC = "CONSENSUSCREATETOPIC"
    CONSENSUSDELETETOPIC = "CONSENSUSDELETETOPIC"
    CONSENSUSSUBMITMESSAGE = "CONSENSUSSUBMITMESSAGE"
    CONSENSUSUPDATETOPIC = "CONSENSUSUPDATETOPIC"
    CONTRACTCALL = "CONTRACTCALL"
    CONTRACTCREATEINSTANCE = "CONTRACTCREATEINSTANCE"
    CONTRACTDELETEINSTANCE = "CONTRACTDELETEINSTANCE"
    CONTRACTUPDATEINSTANCE = "CONTRACTUPDATEINSTANCE"
    CRYPTOADDLIVEHASH = "CRYPTOADDLIVEHASH"
    CRYPTOAPPROVEALLOWANCE = "CRYPTOAPPROVEALLOWANCE"
    CRYPTOCREATEACCOUNT = "CRYPTOCREATEACCOUNT"
    CRYPTODELETE = "CRYPTODELETE"
    CRYPTODELETEALLOWANCE = "CRYPTODELETEALLOWANCE"
    CRYPTODELETELIVEHASH = "CRYPTODELETELIVEHASH"
    CRYPTOTRANSFER = "CRYPTOTRANSFER"
    CRYPTOUPDATEACCOUNT = "CRYPTOUPDATEACCOUNT"
    ETHEREUMTRANSACTION = "ETHEREUMTRANSACTION"
    FILEAPPEND = "FILEAPPEND"
    FILECREATE = "FILECREATE"
    FILEDELETE = "FILEDELETE"
    FILEUPDATE = "FILEUPDATE"
    FREEZE = "FREEZE"
    SCHEDULECREATE = "SCHEDULECREATE"
    SCHEDULEDELETE = "SCHEDULEDELETE"
    SCHEDULESIGN = "SCHEDULESIGN"
    TOKENCREATION = "TOKENCREATION"
    TOKENDELETION = "TOKENDELETION"
    TOKENASSOCIATE = "TOKENASSOCIATE"
    TOKENDISSOCIATE = "TOKENDISSOCIATE"
    TOKENMINT = "TOKENMINT"
    TOKENBURN = "TOKENBURN"
    TOKENWIPE = "TOKENWIPE"
    TOKENFREEZE = "TOKENFREEZE"
    TOKENUNFREEZE = "TOKENUNFREEZE"
    TOKENGRANTKYC = "TOKENGRANTKYC"
    TOKENREVOKEKYC = "TOKENREVOKEKYC"
    TOKENUPDATE = "TOKENUPDATE"
    TOKENAIRDROP = "TOKENAIRDROP"
    TOKENCANCELAIRDROP = "TOKENCANCELAIRDROP"
    TOKENCLAIMAIRDROP = "TOKENCLAIMAIRDROP"
    TOKENREJECT = "TOKENREJECT"
    TOKENPAUSE = "TOKENPAUSE"
    TOKENUNPAUSE = "TOKENUNPAUSE"
    TOKENFEESCHEDULEUPDATE = "TOKENFEESCHEDULEUPDATE"
    TOKENUPDATENFTS = "TOKENUPDATENFTS"
    SYSTEMDELETE = "SYSTEMDELETE"
    SYSTEMUNDELETE = "SYSTEMUNDELETE"
    UNCHECKEDSUBMIT = "UNCHECKEDSUBMIT"
    UTILPRNG = "UTILPRNG"
    UNKNOWN = "UNKNOWN"


class TokenType(str, Enum):
    """Token type enumeration."""
    FUNGIBLE_COMMON = "FUNGIBLE_COMMON"
    NON_FUNGIBLE_UNIQUE = "NON_FUNGIBLE_UNIQUE"


class PauseStatus(str, Enum):
    """Pause status enumeration."""
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PAUSED = "PAUSED"
    UNPAUSED = "UNPAUSED"


class SupplyType(str, Enum):
    """Supply type enumeration."""
    FINITE = "FINITE"
    INFINITE = "INFINITE"


class FreezeStatus(str, Enum):
    """Freeze status enumeration."""
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FROZEN = "FROZEN"
    UNFROZEN = "UNFROZEN"


class KycStatus(str, Enum):
    """KYC status enumeration."""
    NOT_APPLICABLE = "NOT_APPLICABLE"
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"


class Links(BaseModel):
    """Pagination links."""
    next: Optional[str] = None


class Error(BaseModel):
    """API error response."""
    status: Dict[str, Any] = Field(alias="status")


class Key(BaseModel):
    """Cryptographic key information."""
    type: str = Field(alias="_type")
    key: str


class EntityId(BaseModel):
    """Entity ID model."""
    shard: int
    realm: int
    num: int

    @field_validator("shard", "realm", "num", mode="before")
    @classmethod
    def validate_non_negative(cls, v):
        if isinstance(v, str) and v.isdigit():
            v = int(v)
        if not isinstance(v, int) or v < 0:
            raise ValueError("Entity ID components must be non-negative integers")
        return v

    def __str__(self) -> str:
        return f"{self.shard}.{self.realm}.{self.num}"


class TimestampRange(BaseModel):
    """Timestamp range model."""
    from_timestamp: str = Field(alias="from")
    to: Optional[str] = None


class TokenBalance(BaseModel):
    """Token balance information."""
    token_id: str
    balance: int


class AccountBalance(BaseModel):
    """Account balance information."""
    account: str
    balance: int
    tokens: List[TokenBalance] = []


class Balance(BaseModel):
    """Balance information with timestamp."""
    timestamp: Optional[str] = None
    balance: Optional[int] = None
    tokens: List[TokenBalance] = []


class AccountInfo(BaseModel):
    """Account information."""
    account: str
    alias: Optional[str] = None
    auto_renew_period: Optional[int] = None
    balance: Optional[Balance] = None
    created_timestamp: Optional[str] = None
    decline_reward: bool = False
    deleted: Optional[bool] = None
    ethereum_nonce: Optional[int] = None
    evm_address: Optional[str] = None
    expiry_timestamp: Optional[str] = None
    key: Optional[Key] = None
    max_automatic_token_associations: Optional[int] = None
    memo: Optional[str] = None
    pending_reward: Optional[int] = None
    receiver_sig_required: Optional[bool] = None
    staked_account_id: Optional[str] = None
    staked_node_id: Optional[int] = None
    stake_period_start: Optional[str] = None


class AccountsResponse(BaseModel):
    """Response for accounts endpoint."""
    accounts: List[AccountInfo]
    links: Links


class NftTransfer(BaseModel):
    """NFT transfer information."""
    is_approval: bool
    receiver_account_id: Optional[str] = None
    sender_account_id: Optional[str] = None
    serial_number: int
    token_id: str


class TokenTransfer(BaseModel):
    """Token transfer information."""
    token_id: str
    account: str
    amount: int
    is_approval: bool = False


class Transfer(BaseModel):
    """HBAR transfer information."""
    account: str
    amount: int
    is_approval: bool = False


class StakingRewardTransfer(BaseModel):
    """Staking reward transfer information."""
    account: str
    amount: int


class AssessedCustomFee(BaseModel):
    """Assessed custom fee information."""
    amount: int
    collector_account_id: str
    effective_payer_account_ids: List[str] = []
    token_id: Optional[str] = None


class Transaction(BaseModel):
    """Transaction information."""
    bytes: Optional[str] = None
    charged_tx_fee: int
    consensus_timestamp: str
    entity_id: Optional[str] = None
    max_fee: str
    memo_base64: Optional[str] = None
    name: TransactionType
    nft_transfers: List[NftTransfer] = []
    node: Optional[str] = None
    nonce: int = 0
    parent_consensus_timestamp: Optional[str] = None
    result: str
    scheduled: bool = False
    staking_reward_transfers: List[StakingRewardTransfer] = []
    token_transfers: List[TokenTransfer] = []
    transaction_hash: Optional[str] = None
    transaction_id: str
    transfers: List[Transfer] = []
    valid_duration_seconds: Optional[str] = None
    valid_start_timestamp: str


class TransactionDetail(Transaction):
    """Detailed transaction information."""
    assessed_custom_fees: List[AssessedCustomFee] = []


class TransactionsResponse(BaseModel):
    """Response for transactions endpoint."""
    transactions: List[Transaction]
    links: Links


class TransactionByIdResponse(BaseModel):
    """Response for transaction by ID endpoint."""
    transactions: List[TransactionDetail]


class AccountBalanceTransactions(AccountInfo):
    """Account information with transactions."""
    transactions: List[Transaction] = []
    links: Links


class Nft(BaseModel):
    """NFT information."""
    account_id: str
    created_timestamp: Optional[str] = None
    delegating_spender: Optional[str] = None
    deleted: bool = False
    metadata: Optional[str] = None
    modified_timestamp: Optional[str] = None
    serial_number: int
    spender: Optional[str] = None
    token_id: str


class NftsResponse(BaseModel):
    """Response for NFTs endpoint."""
    nfts: List[Nft]
    links: Links


class StakingReward(BaseModel):
    """Staking reward information."""
    account_id: str
    amount: int
    timestamp: str


class StakingRewardsResponse(BaseModel):
    """Response for staking rewards endpoint."""
    rewards: List[StakingReward]
    links: Links


class TokenRelationship(BaseModel):
    """Token relationship information."""
    automatic_association: bool
    balance: int
    created_timestamp: str
    decimals: int
    freeze_status: FreezeStatus
    kyc_status: KycStatus
    token_id: str


class TokenRelationshipResponse(BaseModel):
    """Response for token relationships endpoint."""
    tokens: List[TokenRelationship]
    links: Links


class TokenAirdrop(BaseModel):
    """Token airdrop information."""
    amount: int
    receiver_id: str
    sender_id: str
    serial_number: Optional[int] = None
    timestamp: TimestampRange
    token_id: str


class TokenAirdropsResponse(BaseModel):
    """Response for token airdrops endpoint."""
    airdrops: List[TokenAirdrop]
    links: Links


class Allowance(BaseModel):
    """Base allowance information."""
    amount: int
    amount_granted: int
    owner: str
    spender: str
    timestamp: TimestampRange


class CryptoAllowance(Allowance):
    """Crypto allowance information."""
    pass


class CryptoAllowancesResponse(BaseModel):
    """Response for crypto allowances endpoint."""
    allowances: List[CryptoAllowance]
    links: Links


class TokenAllowance(Allowance):
    """Token allowance information."""
    token_id: str


class TokenAllowancesResponse(BaseModel):
    """Response for token allowances endpoint."""
    allowances: List[TokenAllowance]
    links: Links


class NftAllowance(BaseModel):
    """NFT allowance information."""
    approved_for_all: bool
    owner: str
    spender: str
    timestamp: TimestampRange
    token_id: str


class NftAllowancesResponse(BaseModel):
    """Response for NFT allowances endpoint."""
    allowances: List[NftAllowance]
    links: Links


class BalancesResponse(BaseModel):
    """Response for balances endpoint."""
    timestamp: Optional[str] = None
    balances: List[AccountBalance]
    links: Links


class Block(BaseModel):
    """Block information."""
    count: int
    gas_used: Optional[int] = None
    hapi_version: Optional[str] = None
    hash: str
    logs_bloom: Optional[str] = None
    name: str
    number: int
    previous_hash: str
    size: Optional[int] = None
    timestamp: TimestampRange


class BlocksResponse(BaseModel):
    """Response for blocks endpoint."""
    blocks: List[Block]
    links: Links


class ContractCallRequest(BaseModel):
    """Request for contract call."""
    to: str
    data: Optional[str] = None
    from_address: Optional[str] = Field(None, alias="from")
    gas: Optional[int] = None
    gas_price: Optional[int] = Field(None, alias="gasPrice")
    value: Optional[int] = None
    block: Optional[str] = None
    estimate: Optional[bool] = None


class ContractCallResponse(BaseModel):
    """Response for contract call."""
    result: str


class ContractResultLog(BaseModel):
    """Contract result log."""
    address: str
    bloom: Optional[str] = None
    contract_id: str
    data: Optional[str] = None
    index: int
    topics: List[str] = []


class ContractResultStateChange(BaseModel):
    """Contract result state change."""
    address: str
    contract_id: str
    slot: str
    value_read: str
    value_written: Optional[str] = None


class ContractResult(BaseModel):
    """Contract result information."""
    address: str
    amount: Optional[int] = None
    bloom: Optional[str] = None
    call_result: Optional[str] = None
    contract_id: str
    created_contract_ids: List[str] = []
    error_message: Optional[str] = None
    from_address: Optional[str] = Field(None, alias="from")
    function_parameters: Optional[str] = None
    gas_consumed: Optional[int] = None
    gas_limit: int
    gas_used: Optional[int] = None
    hash: str
    result: str
    timestamp: str
    to: Optional[str] = None


class ContractResultDetails(ContractResult):
    """Detailed contract result information."""
    logs: List[ContractResultLog] = []
    state_changes: List[ContractResultStateChange] = []


class ContractResultsResponse(BaseModel):
    """Response for contract results endpoint."""
    results: List[ContractResult]
    links: Links


class Contract(BaseModel):
    """Contract information."""
    admin_key: Optional[Key] = None
    auto_renew_account: Optional[str] = None
    auto_renew_period: Optional[int] = None
    contract_id: str
    created_timestamp: Optional[str] = None
    deleted: bool = False
    evm_address: str
    expiration_timestamp: Optional[str] = None
    file_id: Optional[str] = None
    max_automatic_token_associations: Optional[int] = None
    memo: Optional[str] = None
    obtainer_id: Optional[str] = None
    permanent_removal: Optional[bool] = None
    proxy_account_id: Optional[str] = None
    timestamp: TimestampRange


class ContractResponse(Contract):
    """Contract response with bytecode."""
    bytecode: Optional[str] = None
    runtime_bytecode: Optional[str] = None


class ContractsResponse(BaseModel):
    """Response for contracts endpoint."""
    contracts: List[Contract]
    links: Links


class ContractState(BaseModel):
    """Contract state information."""
    address: str
    contract_id: str
    timestamp: str
    slot: str
    value: str


class ContractStateResponse(BaseModel):
    """Response for contract state endpoint."""
    state: List[ContractState]
    links: Links


class ContractAction(BaseModel):
    """Contract action information."""
    call_depth: int
    call_operation_type: str
    call_type: str
    caller: str
    caller_type: str
    from_address: str = Field(alias="from")
    gas: int
    gas_used: int
    index: int
    input: Optional[str] = None
    recipient: Optional[str] = None
    recipient_type: Optional[str] = None
    result_data: Optional[str] = None
    result_data_type: str
    timestamp: str
    to: Optional[str] = None
    value: int


class ContractActionsResponse(BaseModel):
    """Response for contract actions endpoint."""
    actions: List[ContractAction]
    links: Links


class ContractLog(BaseModel):
    """Contract log information."""
    address: str
    block_hash: str
    block_number: int
    bloom: Optional[str] = None
    contract_id: str
    data: Optional[str] = None
    index: int
    root_contract_id: str
    timestamp: str
    topics: List[str] = []
    transaction_hash: str
    transaction_index: Optional[int] = None


class ContractLogsResponse(BaseModel):
    """Response for contract logs endpoint."""
    logs: List[ContractLog]
    links: Links


class ExchangeRate(BaseModel):
    """Exchange rate information."""
    cent_equivalent: int
    expiration_time: int
    hbar_equivalent: int


class NetworkExchangeRateSetResponse(BaseModel):
    """Response for network exchange rate endpoint."""
    current_rate: ExchangeRate
    next_rate: ExchangeRate
    timestamp: str


class NetworkFee(BaseModel):
    """Network fee information."""
    gas: int
    transaction_type: str


class NetworkFeesResponse(BaseModel):
    """Response for network fees endpoint."""
    fees: List[NetworkFee]
    timestamp: str


class ServiceEndpoint(BaseModel):
    """Service endpoint information."""
    domain_name: str
    ip_address_v4: str
    port: int


class NetworkNode(BaseModel):
    """Network node information."""
    admin_key: Optional[Key] = None
    decline_reward: Optional[bool] = None
    description: Optional[str] = None
    file_id: str
    max_stake: Optional[int] = None
    memo: Optional[str] = None
    min_stake: Optional[int] = None
    node_account_id: str
    node_id: int
    node_cert_hash: Optional[str] = None
    public_key: Optional[str] = None
    reward_rate_start: Optional[int] = None
    service_endpoints: List[ServiceEndpoint] = []
    stake: Optional[int] = None
    stake_not_rewarded: Optional[int] = None
    stake_rewarded: Optional[int] = None
    staking_period: Optional[TimestampRange] = None
    timestamp: TimestampRange


class NetworkNodesResponse(BaseModel):
    """Response for network nodes endpoint."""
    nodes: List[NetworkNode]
    links: Links


class NetworkStakeResponse(BaseModel):
    """Response for network stake endpoint."""
    max_stake_rewarded: int
    max_staking_reward_rate_per_hbar: int
    max_total_reward: int
    node_reward_fee_fraction: float
    reserved_staking_rewards: int
    reward_balance_threshold: int
    stake_total: int
    staking_period: TimestampRange
    staking_period_duration: int
    staking_periods_stored: int
    staking_reward_fee_fraction: float
    staking_reward_rate: int
    staking_start_threshold: int
    unreserved_staking_reward_balance: int


class NetworkSupplyResponse(BaseModel):
    """Response for network supply endpoint."""
    released_supply: str
    timestamp: str
    total_supply: str


class Schedule(BaseModel):
    """Schedule information."""
    admin_key: Optional[Key] = None
    consensus_timestamp: str
    creator_account_id: str
    deleted: bool = False
    executed_timestamp: Optional[str] = None
    expiration_time: Optional[str] = None
    memo: Optional[str] = None
    payer_account_id: Optional[str] = None
    schedule_id: str
    signatures: List[Dict[str, Any]] = []
    transaction_body: Optional[str] = None
    wait_for_expiry: bool = False


class SchedulesResponse(BaseModel):
    """Response for schedules endpoint."""
    schedules: List[Schedule]
    links: Links


class FixedFee(BaseModel):
    """Fixed fee information."""
    all_collectors_are_exempt: bool = False
    amount: int
    collector_account_id: str
    denominating_token_id: Optional[str] = None


class FractionalFee(BaseModel):
    """Fractional fee information."""
    all_collectors_are_exempt: bool = False
    amount: Dict[str, int]  # numerator and denominator
    collector_account_id: str
    denominating_token_id: Optional[str] = None
    maximum: Optional[int] = None
    minimum: int
    net_of_transfers: bool = False


class RoyaltyFee(BaseModel):
    """Royalty fee information."""
    all_collectors_are_exempt: bool = False
    amount: Dict[str, int]  # numerator and denominator
    collector_account_id: str
    fallback_fee: Optional[Dict[str, Any]] = None


class CustomFees(BaseModel):
    """Custom fees information."""
    created_timestamp: str
    fixed_fees: List[FixedFee] = []
    fractional_fees: List[FractionalFee] = []
    royalty_fees: List[RoyaltyFee] = []


class Token(BaseModel):
    """Token information."""
    admin_key: Optional[Key] = None
    decimals: int
    metadata: Optional[str] = None
    name: str
    symbol: str
    token_id: str
    type: TokenType


class TokenInfo(BaseModel):
    """Detailed token information."""
    admin_key: Optional[Key] = None
    auto_renew_account: Optional[str] = None
    auto_renew_period: Optional[int] = None
    created_timestamp: str
    decimals: str
    deleted: Optional[bool] = None
    expiry_timestamp: Optional[int] = None
    fee_schedule_key: Optional[Key] = None
    freeze_default: bool = False
    freeze_key: Optional[Key] = None
    initial_supply: str
    kyc_key: Optional[Key] = None
    max_supply: str
    metadata: Optional[str] = None
    metadata_key: Optional[Key] = None
    modified_timestamp: str
    name: str
    memo: Optional[str] = None
    pause_key: Optional[Key] = None
    pause_status: PauseStatus
    supply_key: Optional[Key] = None
    supply_type: SupplyType
    symbol: str
    token_id: str
    total_supply: str
    treasury_account_id: str
    type: TokenType
    wipe_key: Optional[Key] = None
    custom_fees: Optional[CustomFees] = None


class TokensResponse(BaseModel):
    """Response for tokens endpoint."""
    tokens: List[Token]
    links: Links


class TokenDistribution(BaseModel):
    """Token distribution information."""
    account: str
    balance: int
    decimals: int


class TokenBalancesResponse(BaseModel):
    """Response for token balances endpoint."""
    timestamp: Optional[str] = None
    balances: List[TokenDistribution]
    links: Links


class NftTransactionTransfer(BaseModel):
    """NFT transaction transfer information."""
    consensus_timestamp: str
    is_approval: bool
    nonce: int
    receiver_account_id: str
    sender_account_id: str
    transaction_id: str
    type: TransactionType


class NftTransactionHistory(BaseModel):
    """NFT transaction history."""
    transactions: List[NftTransactionTransfer]
    links: Links

class InitialTransaction(BaseModel):
    """Initial transaction ID."""
    account_id: str
    nonce: int
    scheduled: bool
    transaction_valid_start: str

class ChunkInfo(BaseModel):
    """Chunk information for topic messages."""
    initial_transaction_id: InitialTransaction
    number: int
    total: int


class TopicMessage(BaseModel):
    """Topic message information."""
    chunk_info: Optional[ChunkInfo] = None
    consensus_timestamp: str
    message: str
    payer_account_id: str
    running_hash: str
    running_hash_version: int
    sequence_number: int
    topic_id: str


class TopicMessagesResponse(BaseModel):
    """Response for topic messages endpoint."""
    messages: List[TopicMessage]
    links: Links


class ConsensusCustomFees(BaseModel):
    """Consensus custom fees information."""
    created_timestamp: str
    fixed_fees: List[FixedFee] = []


class Topic(BaseModel):
    """Topic information."""
    admin_key: Optional[Key] = None
    auto_renew_account: Optional[str] = None
    auto_renew_period: Optional[int] = None
    created_timestamp: Optional[str] = None
    custom_fees: Optional[ConsensusCustomFees] = None
    deleted: Optional[bool] = None
    fee_exempt_key_list: List[Key] = []
    fee_schedule_key: Optional[Key] = None
    memo: Optional[str] = None
    submit_key: Optional[Key] = None
    timestamp: TimestampRange
    topic_id: str