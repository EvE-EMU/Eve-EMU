$(function () {
  $("#id_item_type").autoComplete({
    resolverSettings: {
      url: "/buybackprogram/item_autocomplete/",
    },
  });

  $("#id_eve_solar_system").autoComplete({
    resolverSettings: {
      url: "/buybackprogram/solarsystem_autocomplete/",
    },
  });

  $("#id_marketgroup").autoComplete({
    resolverSettings: {
      url: "/buybackprogram/marketgroup_autocomplete/",
    },
  });

});
