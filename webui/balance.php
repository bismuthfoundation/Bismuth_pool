<?php
require_once '.common.php';

$address = trim(param('address'));


$stmt = $db->prepare('SELECT id FROM addresses WHERE address = ?');
$stmt->execute(array($address));
$address_id = $stmt->fetchColumn();
unset($stmt);
if( empty($address_id) ) {
	header('Location: /');
	exit;
}

$block = $db->query('SELECT * FROM blocks ORDER BY id DESC LIMIT 1')->fetch(PDO::FETCH_ASSOC);

$stmt = $db->prepare('SELECT COUNT(block_id) as total_blocks, SUM(shmeckles) as total_shmeckles, workcount FROM workproof WHERE address_id = ? GROUP BY address_id');
$stmt->execute(array($address_id));
$stats = $stmt->fetch(PDO::FETCH_ASSOC);
unset($stmt);
?>
<pre>
Address: <?= $address ?>

Blocks Helped Mine: <?= $stats['total_blocks'] ?>

Shmeckles: <?= $stats['total_shmeckles'] ?> (<?= round($stats['total_shmeckles'] / $block['pool_shmeckles'] * 100, 4) ?>%)

BIS: <?= ($stats['total_shmeckles'] / $block['pool_shmeckles']) * $block['pool_balance'] ?>

</pre>
