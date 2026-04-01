<template>
  <section>
    <h1>Members</h1>
    <p>Cashier lookup with loyalty and wallet operations.</p>

    <div class="panel">
      <label for="member-search">Member code or name</label>
      <input id="member-search" v-model="search" @keyup.enter="runSearch" placeholder="MEM-001" />
      <button class="btn" @click="runSearch" :disabled="loading">Search</button>
    </div>

    <table class="data-table" v-if="results.length > 0">
      <thead>
        <tr>
          <th>Code</th>
          <th>Name</th>
          <th>Tier</th>
          <th>Points</th>
          <th>Wallet</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="member in results" :key="member.id">
          <td>{{ member.member_code }}</td>
          <td>{{ member.full_name }}</td>
          <td>{{ member.tier }}</td>
          <td>{{ member.points_balance }}</td>
          <td>{{ member.wallet_balance ?? "N/A" }}</td>
          <td>
            <button class="btn btn-small" @click="selectMember(member.member_code)">Select</button>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-if="!loading && results.length === 0">No members found.</p>

    <section v-if="selected" class="panel">
      <h2>Member Details: {{ selected.member_code }}</h2>
      <p>
        Tier: {{ selected.tier }} | Points: {{ selected.points_balance }} | Wallet:
        {{ selected.wallet_balance ?? "N/A" }}
      </p>

      <div class="form-grid">
        <div>
          <h3>Accrue Points</h3>
          <input v-model="preTaxAmount" placeholder="Pre-tax amount (e.g. 19.99)" />
          <input v-model="pointsReason" placeholder="Reason" />
          <button class="btn" @click="onAccruePoints">Apply</button>
        </div>

        <div>
          <h3>Wallet Credit</h3>
          <input v-model="creditAmount" placeholder="Amount" />
          <input v-model="creditReason" placeholder="Reason" />
          <button class="btn" @click="onCreditWallet">Credit</button>
        </div>

        <div>
          <h3>Wallet Debit</h3>
          <input v-model="debitAmount" placeholder="Amount" />
          <input v-model="debitReason" placeholder="Reason" />
          <button class="btn" @click="onDebitWallet">Debit</button>
        </div>
      </div>

      <div class="ledger-grid">
        <div>
          <h3>Points Ledger</h3>
          <ul>
            <li v-for="entry in pointsLedger" :key="entry.id">
              {{ entry.points_delta }} pts - {{ entry.reason }}
            </li>
          </ul>
        </div>
        <div>
          <h3>Wallet Ledger</h3>
          <ul>
            <li v-for="entry in walletLedger" :key="entry.id">
              {{ entry.entry_type }} {{ entry.amount }} -> {{ entry.balance_after }} ({{
                entry.reason
              }})
            </li>
          </ul>
        </div>
      </div>
    </section>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";

import {
  accruePoints,
  creditWallet,
  debitWallet,
  fetchPointsLedger,
  fetchWalletLedger,
  getMember,
  searchMembers,
  type MemberRecord,
  type PointsLedgerEntry,
  type WalletLedgerEntry,
} from "@/services/members";
import { useUiStore } from "@/stores/ui";
import { notifyError } from "@/utils/feedback";

const ui = useUiStore();

const loading = ref(false);
const errorMessage = ref("");
const search = ref("");
const results = ref<MemberRecord[]>([]);
const selected = ref<MemberRecord | null>(null);
const pointsLedger = ref<PointsLedgerEntry[]>([]);
const walletLedger = ref<WalletLedgerEntry[]>([]);

const preTaxAmount = ref("19.99");
const pointsReason = ref("purchase");
const creditAmount = ref("10.00");
const creditReason = ref("top up");
const debitAmount = ref("5.00");
const debitReason = ref("purchase");

async function runSearch() {
  loading.value = true;
  errorMessage.value = "";
  try {
    results.value = await searchMembers(search.value || undefined);
  } catch (error) {
    errorMessage.value = notifyError(error, "Member search failed.");
  } finally {
    loading.value = false;
  }
}

async function refreshSelected(memberCode: string) {
  selected.value = await getMember(memberCode);
  pointsLedger.value = await fetchPointsLedger(memberCode);
  walletLedger.value = await fetchWalletLedger(memberCode);
}

async function selectMember(memberCode: string) {
  errorMessage.value = "";
  try {
    await refreshSelected(memberCode);
  } catch (error) {
    errorMessage.value = notifyError(error, "Failed to load member details.");
  }
}

async function onAccruePoints() {
  if (!selected.value) return;
  try {
    await accruePoints(selected.value.member_code, preTaxAmount.value, pointsReason.value);
    await refreshSelected(selected.value.member_code);
    await runSearch();
    ui.success("Posted", "Points accrual posted and balances refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Points accrual failed.");
  }
}

async function onCreditWallet() {
  if (!selected.value) return;
  try {
    await creditWallet(selected.value.member_code, creditAmount.value, creditReason.value);
    await refreshSelected(selected.value.member_code);
    await runSearch();
    ui.success("Posted", "Wallet credit posted and balances refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Wallet credit failed.");
  }
}

async function onDebitWallet() {
  if (!selected.value) return;
  try {
    await debitWallet(selected.value.member_code, debitAmount.value, debitReason.value);
    await refreshSelected(selected.value.member_code);
    await runSearch();
    ui.success("Posted", "Wallet debit posted and balances refreshed.");
  } catch (error) {
    errorMessage.value = notifyError(error, "Wallet debit failed.");
  }
}
</script>
