export const IframeDemo = () => {
  // draft values (edited live)
  const [draftChain, setDraftChain] = useState("solana");
  const [draftAddress, setDraftAddress] = useState(
    "FQgtfugBdpFN7PZ6NdPrZpVLDBrPGxXesi4gVu3vErhY"
  );

  // applied values (drive the iframe)
  const [chain, setChain] = useState(draftChain);
  const [address, setAddress] = useState(draftAddress);

  const url = useMemo(
    () =>
      `https://iframe.bubblemaps.io/map?address=${address}&chain=${chain}&partnerId=demo`,
    [address, chain]
  );

  // true when there is nothing new to apply
  const isStale = draftChain === chain && draftAddress === address;

  const handleApply = () => {
    if (isStale) return; // extra safety
    setChain(draftChain);
    setAddress(draftAddress);
  };

  return (
    <div className="my-6">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          className="border rounded p-2"
          value={draftChain}
          onChange={(e) => setDraftChain(e.target.value)}
        >
          {[
            { value: "solana", label: "Solana" },
            { value: "eth", label: "Ethereum" },
            { value: "bsc", label: "BNB Chain" },
            { value: "tron", label: "Tron" },
            { value: "base", label: "Base" },
            { value: "apechain", label: "Apechain" },
            { value: "sonic", label: "Sonic" },
            { value: "ton", label: "TON" },
            { value: "avalanche", label: "Avalanche" },
            { value: "polygon", label: "Polygon" },
            { value: "monad", label: "Monad" },
          ].map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>

        <input
          className="border rounded p-2 flex-1 min-w-[260px]"
          type="text"
          value={draftAddress}
          onChange={(e) => setDraftAddress(e.target.value)}
        />

        <button
          disabled={isStale}
          onClick={handleApply}
          className={`rounded p-2 transition-colors ${
            isStale
              ? "bg-gray-300 text-gray-500 cursor-not-allowed"
              : "bg-pink-600 hover:bg-pink-700 text-white"
          }`}
        >
          Apply
        </button>
      </div>

      <iframe
        src={url}
        style={{
          width: "100%",
          height: 600,
          border: "none",
          borderRadius: "10px",
        }}
      />
    </div>
  );
};
